# 当前 Goal 与证据状态

原研究 Goal 仍为 active，当前执行依据为 revision 6，源自 GitHub 主分支提交 `7024de8b589c1fca67c66a7d29d11cda60af4a9c`。M1 的 Diversity 正式路径、ContractNLI 合同接口学习与复用、M2 的 OpenExempt 候选驱动选组均已接通。两项贡献仍需通过同信息强对照证明各自的原生收益。连续账本 15,400 笔，其中完成 15,363 笔、历史失败 37 笔，在途 0。冻结协议、TEST 结果和曝光记录保留。 [实测断点](NEW_CHAT_HANDOFF.md)

[主分支当前方案](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legal_skill_convergence_20261117/PLAN.md) · [主分支接续配置](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json) · [Revision 6 进展与验收缺口](../reports/legal_skill_convergence_20261117/GOAL_BLOCK_REVISION6_20261119.md)

## Revision 6 ContractNLI 跨条款引文和 B5 采纳的后批验证

把跨多个独立条款的连续引用收敛到已核验的限用途句。复用 B5 前缀的 30 笔实测重拟合，复现各策略原选组和采纳。给各路完整原文证据后，B6 的候选驱动分类为 3/3，时间和分歧对照均为 2/3，正确类证据 F1 为 71.11% 对 66.67%。在随后六份 B7–B8 原 TRAIN 上，三路分类均为 6/6，正确类证据 F1 为 57.78% 对 74.44%。B6–B8 合计为 9/9 对 8/9，证据 F1 为 62.22% 对 71.85%。固定 DEV 与 M1 匹配比较沿用。复用 48 笔，新增 0。 [原生配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_RANGE_AND_B5_TRANSFER_20261120.json)

## Revision 6 ContractNLI 限用途条款的主体与全文核验

将编号用语绑定到条款前导中的义务主体与保密对象，并核对全文中的非用途义务。原 TRAIN 五条唯一用途链和两份用途未提及均匹配参考。固定 DEV 五臂用途题各由 13/16 到 15/16，零退化。ContractNLI 累计四内部臂 235/272、证据 F1 67.30%，PARSE 223/272、60.34%。M1 后批对最强匹配对照的正确类证据 F1 差 +2.78 个百分点，区间跨零。已锁定的 M2 前向三份中候选驱动为 3/3，其余为 2/3，正确类证据 F1 为 39.20% 对 55.56%。新增请求 0。 [同信息配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_GOVERNED_USE_PURPOSE_TRAIN_DEV_20261120.json)

## Revision 6 Airline 真实提案与公开费率执行

将已核验的公开费率、票价和完整行李清单接入修订版执行器。复用 58 笔物理响应，覆盖原八批 24 份 TRAIN 及普通教师、PARSE 的 16 项实测提案。各臂的进入程序和提案均为 7/24，所有提案均未采纳。共用原文执行在 TRAIN 为 24/24；原固定 DEV 的 16 份在每个原 B8 臂均实际调用这一分支，五臂各保持 16/16，新增模型请求 0。其他库累计沿用。 [逐批提案与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_AIRLINE_CANDIDATE_ARCHIVE_TRAIN_DEV_20261120.json)

## Revision 6 M1 MAUD 例外前导与契约族解码

复用 36 笔 TRAIN 和 39 笔固定 DEV 同输入读数。按题面前导定位疫情条件及其义务，原 TRAIN 核实 8 项，全部匹配参考，固定 DEV 5 项中 4 项匹配。将同一契约族的多个锚点合并后，额外恢复一项符合 DEV 标签的肯定输出，原文的编号列表明确将该条件排除在负面义务之外。给各路同一原文核验后，合成、固定字段、直接读法在已覆盖的 26 项上为 16/26、20/26、20/26。五库正式累计沿用。新增请求 0。 [配对与累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_PREAMBLE_ATTACHMENT_TRAIN_DEV_20261120.json)

## Revision 6 M2 OpenExempt 俄勒冈服饰条文

将服饰修正绑定到原请求中的条文正文与资产，排除错误的车辆和家庭动物条款。7 份原 TRAIN 和 2 份固定 DEV 上，每任务分别核实 52 项和 26 项，均匹配原参考。复用 144 笔 TRAIN 和 2 笔受影响的 DEV 响应，新增 0。各路共享核验后，16 份后批 TRAIN 上候选驱动与时间、分歧及纯原生拟合逐资产申报一致，分类／估值 F1 为 72.98%／64.98%。固定 DEV 五臂各纠正一份分类，零退化，四内部臂分类 F1 从 86.65% 到 87.17%，PARSE 从 86.08% 到 86.60%，估值持平。 [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_OREGON_APPAREL_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 M2 OpenExempt 威斯康星营业资产作用域

按题面条文分别核验营业设备、企业权益、存款账户和自住房。在六份原 TRAIN 和三份固定 DEV 上，每个任务分别核实 56 项和 28 项申报，全部与参考匹配。B7 反证筛选的候选驱动与按时间保留同一分类程序，选择不同估值程序。给各路共用原文修正后，16 份后批案例上两者实质相同，分类／估值 F1 为 70.87%／62.71%。共用修正后的修复见证门槛达到 72.98%／62.51%，比纯原生拟合平均高 2.86 个百分点，95% 配对区间 [+0.07, +6.74]，同预算时间和分歧对照逐资产相同。固定 DEV 五臂输出保持，新增 0。 [原生结果及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_WI_BUSINESS_PROPERTY_TRAIN_DEV_20261120.json)

## Revision 6 M2 OpenExempt 只按已核实反证采纳

四次原 TRAIN 过渡中，每条同预算策略均从同一候选池选两组。允许原生拟合为正且未发现新错误的候选进入。B7 候选驱动选 PARSE 估值，按时间选普通提案，后批两份结果仅改变申报顺序。在全部 16 份后批案例上，各条筛选策略及原生拟合的逐资产申报及重复计数相同，分类／估值 F1 为 65.77%／59.50%。维持进入程序及先前要求修复见证的筛选为 71.68%／61.04%。双指标平均差 −3.73 个百分点，母来源配对 95% 区间 [−7.65, −0.71]。复用 144 笔原响应，新增 0，固定 DEV 沿用。 [采纳决定及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_REFUTATION_PORTFOLIO_TRAIN_20261120.json)

## Revision 6 ContractNLI 受领类别的定义与外部成员

把披露许可与定义中的顾问、承包商及编号例外绑定。原 TRAIN 有四份明确授权，分类均匹配，三份引文精确匹配；另有一份在受控关联方许可与第三方禁令并存时保留两种解释。后批 12 份的合成、固定、直接为 11/12、10/12、11/12。原 B4 七种策略的选组与采纳维持，候选驱动和按时间逐题一致，均为 58/60，正确类证据 F1 为 91.65%。固定 DEV 命中一份，五臂均已正确引用，五库累计沿用。新增请求 0。 [配对结果与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DEFINED_DISCLOSURE_AUDIENCE_TRAIN_DEV_20261120.json)

## Revision 6 ContractNLI 复制与传递例外的作用范围

把明确准许为约定目的制作副本的分项连回受领方前导，并将按需知悉的传递例外绑定到指定受领人。原 TRAIN 2/24 命中，分类和引文均匹配。两份后批原复制动作比较中，合成保持 2/2，共同核验将固定与直接读法各从 1/2 恢复到 2/2。原 B4 七种选组后批各从 57/60 到 58/60，候选驱动与按时间逐题一致，正确类证据 F1 从 88.59% 到 91.09%。固定 DEV 无覆盖，五库累计沿用，新增请求 0。 [原生配对和五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_EXCEPTION_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 ContractNLI 限定受领人的第三方披露许可

将按需知悉、受领人保密承诺及披露方事先同意分别绑定到其适用分项。四份原 TRAIN 的分类和引文均精确匹配参考。后批 12 份同输入合同上，合成与直接读法均由 7/12 升至 10/12，固定字段为 9/12，归档整文对照为 11/12。原 B4 的七种策略组、采纳和后批逐题程序均保持，候选驱动与按时间逐题一致，60 项各为 57/60，正确类证据 F1 由 87.48% 升至 88.59%。固定 DEV 无命中，五库指标沿用。新增请求 0。 [原生比较及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_LIMITED_AUDIENCE_TRAIN_DEV_20261120.json)

## Revision 6 ContractNLI 定义分项与序言绑定

将同一保护定义下可核实的非技术分项合并，只有在正文定义与披露方一致时才使用列举商业类别的序言。原 TRAIN 覆盖 3/24，三份分类与参考一致，两份引文完全匹配。六份历史同输入比较在统一全文核验后，合成、固定字段、直接为 6/6、4/6、6/6，证据 F1 为 94.81%、61.48%、94.81%；合成和直接逐题相同。原 B8 PARSE 进入程序与提案均为 2/3，证据 F1 为 66.67% 和 33.33%。固定 DEV 无覆盖，五库累计沿用。复用 30 笔读数，新增 0。 [配对、固定 DEV 和五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DEFINITION_EVIDENCE_PATHS_TRAIN_DEV_20261120.json)

## Revision 6 M2 OpenExempt 法条级候选采纳

按题面法条限制分类或估值更新的转移范围，在 B3、B4、B6、B7 四批共享同一候选池、核验规则和双组选组预算。116 个候选中，51 个在当批原生拟合为正，1 个有原文支持的修正。B7 候选驱动与分歧及风险选中同一俄勒冈分类更新，按时间保留进入程序。原 B8 无该法条，16 份后批候选驱动及所有同范围对照输出一致，分类／估值 F1 为 71.68%／61.04%。固定 DEV 沿用，复用 144 笔原响应，新增 0。 [按法条的拟合与前向比较](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_STATUTE_PORTFOLIO_TRAIN_20261120.json)

## Revision 6 ContractNLI 协议事实的条款作用域

新共用核验区分协议事实、保密材料已提供的事实、其他义务与拟议交易，命中 7/24 份 TRAIN、7/16 份固定 DEV，均与原参考一致。固定 DEV 的协议事实题四个内部臂各由 7/16 至 13/16，PARSE 由 11/16 至 15/16，无分类退化。ContractNLI 累计四臂 233/272、证据 F1 66.56%，PARSE 221/272、59.49%。其余四库沿用。

复用 21 笔原配对读数，合成、固定字段、直接作答在共用核验下为 5/7、6/7、6/7。M2 在原 B4 重拟合后，与按时间选组在 12 份后批 TRAIN 上逐题一致，原五题为 57/60、证据 F1 87.48%，另核对协议事实题 12/12、88.89%。新增 0。 [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_AGREEMENT_FACT_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 ContractNLI 口头信息的定义与后续传播

区分保密信息形成时的传达形式与后续传播禁令。核验命中 1/24 份 TRAIN、2/16 份固定 DEV，分类和引文均匹配原参考。B8 口头题四个实际候选读器均为 3/3、正确类证据 F1 88.89%，上一轮 PARSE 提案的单合同分类差由共用证据解释。固定 DEV 四个内部臂口头题由 14/16 到 15/16，PARSE 仍为 11/16，五路引文 F1 各增加 8.93 个百分点。ContractNLI 累计四个内部臂 227/272、证据 F1 64.36%，PARSE 217/272、57.29%。复用 16 笔真实响应，新增 0，其他四库沿用。 [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_ORAL_INFORMATION_SCOPE_TRAIN_DEV_20261120.json)

## Revision 6 M2 ContractNLI B6–B8 已测候选的剩余差异

在原始同输入的 36 笔读数上，B6 权利题的普通和 PARSE 两个提案各自与进入程序同分。B7 第三方披露四路均为 3/3、正确类证据 F1 100%。B8 非技术类别的最强进入程序为 3/3，PARSE 提案为 2/3；口头形式的 PARSE 提案为 3/3，其余为 2/3，正确类证据 F1 均为 55.56%。新增 0。保留 B8 的单合同分类差和另一份提案的长度截断，原历史采纳决定及固定 DEV 沿用。 [实际读数及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_LATE_CANDIDATE_RESIDUALS_TRAIN_20261120.json)

## Revision 6 ContractNLI 权利引文补齐

将既有知识产权归属、披露后新生专利权和保密信息专属所有权分别绑定到同一主体与配套条款。识别的四份后批原 TRAIN 均与原参考引文一致。复用 45 笔真实读数，对每路应用同一引文核验。后批合成、固定字段和同输入直接正确类证据 F1 由 75.00%、75.56%、73.06% 升至 83.33%、83.89%、75.83%，三路均为 12/12。合成相对直接差 +7.50 个百分点，95% 配对区间 [+2.22,+13.89]。相对固定字段差 −0.56，区间 [−4.17,+2.50]。固定 DEV 0/16 命中，原 M2 B4 拟合源无匹配，五库累计沿用。 [配对结果和覆盖](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RIGHTS_CITATION_LINKS_TRAIN_DEV_20261120.json)

## Revision 6 M1 跨条款权利见证

将明示非授予、保密信息所有权、披露所生专利权与相竞争的授权分开读取。合成接口将每类见证的操作效力、对象和主体方向压成一个关系，声明域 27 个状态均等价。冻结读者在 12 份后批原 TRAIN 及三份早批作用域排除对照上完成三路同输入比较。

统一原文核验后，后批合成、固定字段和直接读器均为 12/12，正确类证据 F1 分别为 75.00%、75.56%、73.06%。合成相对固定 −0.56 个百分点、相对直接 +1.94，两个配对区间均跨零。三份早批对照的三路原始读数均错误，由共用核验恢复至 3/3。45 笔实际响应，共 255,398 tokens，无解码失败。候选保留于 TRAIN 库，五库累计固定 DEV 沿用。 [匹配对照、原始读数及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_LINKED_RIGHTS_TRAIN_20261120.json)

## Revision 6 ContractNLI 权利授予的条款作用对象

逐条区分救济、管辖与转让、签署人职务、公司股权和系统访问。原文与索引的线索覆盖一致，至少有一处可核验的作用域，且没有残留权利线索时才判为未提及。保留明示权利条款及未决的借用和局部非授予。命中 TRAIN 3/24、固定 DEV 2/16，均匹配原参考。固定 DEV 五臂权利题由 9/16 到 11/16，零退化。累计四内部臂 226/272、证据 F1 63.83%，PARSE 217/272、56.76%。其他四库沿用。

同一核验给原 24 份 TRAIN 的配对读器后，合成、固定、整文分别为 19/24、20/24、18/24。后批 12 份的 M1 路由和同预算固定路由均为 8/12，归档整文为 11/12，核验没有触发。该修订纳入共用流程。M2 已结算的 B4 后批五题范围不含权利授予。复用 72 笔索引读数、17 笔路由读数，以及 6 笔受影响的正式 TRAIN、4 笔固定 DEV，新增 0。 [配对及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RIGHTS_CONTEXT_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 ContractNLI 双组选组的反证作用域

将原 B4 组合筛选的否决绑定到支持它的具体条款角色。各策略沿用原两组预算、拟合排序和实际读器，单份合同的缺席判断留在原案。候选驱动原先替换的三类题目中，两类缺少可迁移的角色证据。后批 12 份合同上，作用域筛选生效五次，改变四项输出，正确数仍为 57/60，正确类证据 F1 由 83.19% 升至 86.93%。相对同作用域的时间选组与原生拟合高 1.11 个百分点，配对区间 [0,+3.33]。

差异仅来自 B8 第三份合同的对外知悉例外。把可核实的总则和例外引文同样给每路后，候选驱动、时间、领先程序计数、作用域内分歧和原生拟合逐题一致，均为 57/60 和 87.48% 证据 F1。固定 DEV 无同型条款，五库累计沿用。复用 60 笔拟合与 22 笔后批读数，新增 0。 [配对和原文归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PORTFOLIO_SCOPED_VETO_TRAIN_20261120.json)

## Revision 6 OpenExempt B6 类别和估价资产键

复用 B6 真实进入程序、普通提案、PARSE 提案的 24 笔原读数。将亚利桑那手表条款和伊利诺伊服装、职业工具条款的误引绑定到具体资产。PARSE 分类相对进入程序的 +8.52 个百分点，在各路统一排除误引后剩 +0.74。将完整名称和金额均唯一匹配的估价后缀归并后，进入程序为 75.73%，PARSE 为 74.39%，差 −1.34 个百分点。四种同预算筛选均保留进入程序。纯原生拟合从 PARSE 分类加普通估值改为仅普通估值。B7–B8 八份原 TRAIN 无目标法域。

固定 DEV 另核实 3 笔物理响应。受影响的资产键归并后，五臂的原生指标均持平，其他四库沿用。两步复用同一 B6 原读数，新增请求 0。 [分阶段拟合、配对和五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B6_ITEM_CATEGORY_AND_VALUATION_KEYS_20261120.json)

## Revision 6 ContractNLI 标记词的作用对象

把签署人职务、通知收件人、指定区域、商标和销毁确认限定到自己的作用对象。全文与索引的标记词核对一致且全部剩余线索均可归类时，才判定原始信息的标记义务未提及。原 TRAIN 覆盖 8/24、固定 DEV 覆盖 4/16，全部与原标签一致。五臂固定 DEV 标记题均由 12/16 到 16/16，零退化。ContractNLI 累计四内部臂 224/272、证据 F1 63.10%，PARSE 215/272、56.03%。其他四库沿用。

新作用域未命中原六份 M1 定向合同比较，归档读器结果沿用。M2 在原 B4 四读器和 54 对可行组上重拟合，组、采纳及后批预测均复现，后批各为 57/60。保留为共用修订，新增请求 0。 [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DESIGNATION_CUE_ROLES_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 第三方披露的批准条件

区分独立披露许可、事前授权、员工专属访问和法定强制披露，并保存实际约束所需的前导与分项。原 TRAIN 五份、固定 DEV 两份与原分类及引文一致。固定 DEV 五臂各修正两项分类，零退化。ContractNLI 累计四内部臂 220/272、证据 F1 61.63%，PARSE 211/272、54.56%。其他四库沿用。

把同一原文核验给 M1 的后批转移读法及强对照，合成、固定、直接的两项合计分别为 7/24、17/24、6/24，两个归档整文对照均为 20/24。M2 用新公共证据重拟合原 B4 四读器，54 对可行组中各策略所选组和程序均保持。原 B5–B8 的 60 项上各路为 57/60，候选驱动正确类证据 F1 为 83.19%，强对照为 84.23% 至 86.28%。新增请求 0。 [两项对照和五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DISCLOSURE_AUTHORIZATION_AND_FIXED_DEV_20261120.json)

## Revision 6 OpenExempt 威斯康星州消费品与 B8 采纳

按题面消费品条款、个人用途和产权条件核对项目，将自住不动产留在条款作用域之外。B8 第四组核实四项分类和四项估值，固定 DEV 核实三项分类和三项估值，全部匹配原参考。在沿用现有原文修订的前提下，PARSE 分类单独更换仍有两项经原文证实的修正。把新增见证用于筛选时，四个筛选策略均采纳 PARSE 分类和普通提案估值，在 16 份固定 DEV 上均为 73.62%／69.23% F1。先把可核实主张统一补给各路，再拟合和筛选时，四路均保留进入程序，分类／估值 F1 为 67.80%／63.78%。相对仅按原生拟合的平均差为 −5.63 个百分点，95% 配对区间 [−13.37,−0.70]。M2 与时间、分歧两条同预算强对照逐题一致。

共用修订使累计固定 DEV 的 OpenExempt 分类 F1 在五臂各提高 0.625 个百分点，一份改善、零退化。四个内部臂达 86.65%，PARSE 达 86.08%，估值沿用。40 笔 TRAIN 及 96 笔同输入 DEV 原响应复用，新增 0。 [拟合与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_WI_CONSUMER_GOODS_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 到期与保留义务

按原文区分签署后的固定到期、协议实际终止及保留材料的延续义务。对无延续判断核对全文提示及其作用对象，对有延续判断保存直接义务引文和关联条款。适用的三份原 TRAIN、四份固定 DEV 均与原分类及引文一致。固定 DEV 上，存续题四内部臂各由 12/16 到 13/16，PARSE 由 11/16 到 12/16，五臂正确类证据 F1 均由 43.75% 升至 56.25%，零退化。ContractNLI 五库累计中的四内部臂为 218/272、证据 F1 60.89%，PARSE 为 209/272、54.01%。共用修订，其他四库沿用。复用 8 笔响应，新增 0。 [配对与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SURVIVAL_TERM_SCOPE_AND_FIXED_DEV_20261120.json)

## Revision 6 OpenExempt 俄勒冈个人财产

在明示单人所有权下，用原请求的 § 18.345(1)(p) 和逐资产估值口径恢复现有词表漏掉的动产。原 TRAIN 核实四项分类、五项估值，固定 DEV 核实一项估值，均匹配原参考。B4 的五条组合筛选证据改变，候选驱动和各对照的采纳决定维持，其他三个原批次的新增见证也无选型变化。给每路同一投影后，在 16 份后批 TRAIN 上，候选驱动、按时间和按答案分歧逐题一致，分类／估值 F1 均为 70.75%／57.89%。相对仅按原生拟合的两项平均配对差为 +3.35 个百分点，95% 区间 [+0.68,+7.09]。这项差异与两个同预算强对照相同，M2 独立收益仍待验收。

OpenExempt 固定 DEV 的 PARSE 估值 F1 由 79.26% 升至 79.56%，一份改善、零退化，四个内部臂保持 86.03% 分类 F1 和 83.50% 估值 F1。保留为共用修订。复用 144 笔 TRAIN、1 笔固定 DEV，新增请求 0。 [配对与五库累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_OREGON_TANGIBLE_TRAIN_DEV_20261120.json)

## Revision 6 M1 ContractNLI 分槽留存证据

把处分后的保留许可和全量处置禁止分别绑定到各自的引文，穷举确认原消费者 243 个状态保持等价。三份早批原 TRAIN 上复用九笔归档，新增三笔。各路共用原文依据后分类均为 3/3，合成、固定字段、直接读法的正确类证据 F1 分别为 61.11%、57.78%、59.26%。锁定该接口后，在三份预先登记的后批原 TRAIN 新增九笔，同一全文和索引下三路均正确 2/3，证据 F1 分别为 66.67%、27.78%、50.00%。对两个强对照的配对区间下界均为零，相对直接读法的提升集中于 B5 的一份合同。五库固定 DEV 沿用。 [早批锁定](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RETENTION_WITNESSES_FIT_TRAIN_20261120.json) · [同输入后批结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RETENTION_WITNESSES_FORWARD_TRAIN_20261120.json)

## Revision 6 ContractNLI 法定披露与通知覆盖

把法定披露例外与通用送达、终止、地址变更和安全事件通知分开。明示通知法务的条款须绑定到信息提供方。新规则覆盖一份原 TRAIN 和五份固定 DEV，六份均与原分类一致。固定 DEV 五臂的通知题均由 12/16 升至 16/16，正确类证据 F1 由 68.75% 升至 93.75%，零退化。ContractNLI 累计四内部臂为 217/272、证据 F1 60.16%，PARSE 为 208/272、53.27%。在这批原 TRAIN 中，23/24 份可由共用原文核验判定，仅 B2 第一份保留未决，B5–B8 无未决样本可供本项 M1 前向配对。其他四库沿用，新增模型请求 0。 [通知证据与五库累计 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_NOTICE_COVERAGE_LINKS_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 ContractNLI 双组选取

在 B4 和 B5 原四读器候选池中，各筛选策略使用两组、八笔相同预算。候选驱动优先覆盖已知领先程序的反证，再保留更多未被排除的备选程序。B4 共 54 对可行组，候选驱动选 B3 第二组和 B4 第二组，逐题程序与六条对照分别不同。复用 35 笔精确后批响应，在 12 份原 TRAIN 的 60 项上，候选驱动为 55/60，六条对照均为 54/60。唯一分类差来自明示向承包商披露的许可。把三条经原文核对的同类许可给每路后，全部为 55/60。候选驱动的正确类证据 F1 为 79.86%，对照为 80.89% 至 82.94%。B5 的候选驱动与直接冲突覆盖、领先程序反证计数逐题配置相同。固定 DEV 公开输入无新增同型许可。新增请求 0，五库累计 DEV 沿用。 [双组选取与同信息配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COMPLEMENTARY_ACQUISITION_TRAIN_20261120.json)

## Revision 6 ContractNLI 完整处置与留存

核对同一请求下的完整交还与销毁分项，排除有形副本限定和相竞争的留存例外。原 TRAIN 8/24 份有明确全量处置证据，四份为已有规则覆盖，四份由新规则覆盖。八份分类均与参考一致。固定 DEV 一份命中，五臂各修正同一项留存分类和引文，零退化。ContractNLI 累计四内部臂为 213/272、证据 F1 58.69%，PARSE 为 204/272、51.80%。给原 B5 M2 两路同一规则后，候选驱动和按时间的固定 DEV 留存分类各由 5/16、7/16 升到 6/16、8/16。其他四库沿用，新增模型请求 0。 [留存配对和五库累计 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COMPLETE_DISPOSITION_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 ContractNLI B5 合并候选

合并 B5 普通与 PARSE 的两个实际提案及各自进入程序，验证 60 笔前缀读数。B1 首组的普通提案响应未完整解码，保留归档并对所有策略使用同一 14 组完整前缀和每组四笔预算。候选驱动、两种答案分歧对照和原文分类冲突计数均选 B2 第一组，并锁定相同的逐题程序。后批九份原 TRAIN、七个受选型影响的假设共 63 项，四路逐题一致，均为 56/63、正确类证据 F1 81.64%。按时间和原生拟合均为 56/63、82.17%，按作用域内答案及引文分歧为 57/63、79.01%。44 项由共用原文规则直接确定。复用 24 笔后批读数，新增模型请求 0，五库固定 DEV 沿用。 [B5 选组及后批配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B5_CANDIDATE_CONFLICTS_TRAIN_20261120.json)

## Revision 6 ContractNLI 员工许可链

两条共用规则分别绑定明示员工许可和已有的唯一许可链。明示许可覆盖原 TRAIN 4/24，四份分类及许可句匹配参考，三份完整引文精确匹配，固定 DEV 未触发。把该规则同样给 B4 联合候选和全部对照，后批五种策略均为 26/27。候选驱动与两种分歧控制仍逐题一致，证据 F1 为 91.85%，按时间与原生拟合为 92.67%。许可链恢复另覆盖原 TRAIN 2/24、固定 DEV 5/16。在固定 DEV 上五臂均修正一项分类、改善两项证据，零退化。ContractNLI 累计四内部臂为 212/272、证据 F1 58.50%，PARSE 为 203/272、51.54%。其他四库沿用。两轮均无新增模型请求。 [TRAIN 归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EMPLOYEE_PERMISSION_TRAIN_DEV_20261120.json) · [五库累计 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EMPLOYEE_WITNESS_PROJECTION_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 ContractNLI B4 联合候选比较

将普通和 PARSE 两个 B4 提案与各自进入程序合并，按题比较四个实际读器。各筛选策略使用相同的每组四笔读数与共用原文判据。候选驱动与两种按分歧筛选选择了相同组，逐题程序和预测均一致。后批 B6–B8 九份合同、27 项受选型影响的判断上，三路均为 25/27、正确类证据 F1 85.19%，按时间与原生拟合均为 26/27、80.19%。相对原生拟合，分类差 −3.70、证据 F1 差 +4.99 个百分点，95% 配对区间分别为 [−11.11, 0] 和 [−1.28, +13.12]。说明性地去掉一份对照引用 67 段的合同，证据差为 +1.57 个百分点。本轮未建立 M2 的独立收益。复用 79 笔原 TRAIN 读数，新增 1 笔（12,112 tokens），固定 DEV 沿用。 [锁定与后批结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B4_CANDIDATE_PORTFOLIO_TRAIN_20261120.json)

## Revision 6 M1 MAUD 原关系接口固定 DEV

锁定在原后批 TRAIN 答对 17/18 的条款关系接口。16 份原固定 DEV 中 13 份有可见疫情标记及两类契约锚点，统一原文核验后合成、固定字段、直接读法分别为 11/26、21/26、20/26。合成相对两个强对照的母来源配对差为 −38.46、−34.62 个百分点，两个区间上界均为 −15.38。 50 个标记中 30 个被排除两类作用域，13 个重复同一家族。复用原去重规则后合成恢复到 14/26，原锚点组及增补锚点组均低于强对照。五库累计 DEV 沿用。 [实测配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_LOCKED_OPERATIVE_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 本协议终止与存续义务

把本协议的终止前件与继续生效的义务分开核对。两份原 TRAIN 复现已有见证，另命中三份原固定 DEV，五份均与原分类及义务引文一致。固定 DEV 的正确类引文 F1，四内部臂从 39.58% 升到 43.75%，PARSE 从 35.83% 升到 43.75%，五臂零退化。包含终止前件的完整路径记录也保留；把前件列为另一条基准引文时，一份合同评分下降。 ContractNLI 累计分类为四内部臂 211/272、PARSE 202/272，引文 F1 更新为 57.91% 和 50.99%。 [五库累计与逐臂配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SURVIVAL_TRIGGER_ROLES_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 OpenExempt B8 单项豁免见证

在 B8 第四组，原文核实 PARSE 新增两项联邦适用分类，并核实普通提案补报一笔正确估值、另有一笔超过 B7 已校准的单项上限。加入见证后，候选驱动、按时间、按分歧均采纳分类更新，估值保留进入程序。16 份固定 DEV 上分类／估值 F1 为 72.68%／62.63%，原生拟合为 72.68%／68.40%，两项平均差 −2.88 个百分点，配对区间 [−5.73, −0.52]。 同一条文修正给各路后，四种筛选均保留进入程序。原五臂累计 DEV 逐题输出保持一致。原 B8 TRAIN 六项、固定 DEV 九项可核实主张均匹配原参考，所有权未决的资产保持未决。 [原结果与共用修正配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B8_ITEM_WITNESSES_TRAIN_DEV_20261120.json)

## Revision 6 M2 OpenExempt B8 同输入固定 DEV

OpenExempt B8 四个筛选策略均保留进入程序。16 份固定 DEV 使用相同的 B8 法域与资产输入，在同一套原文核验下，筛选、原生拟合、原正式采纳三路的分类／估值 F1 分别为 66.47%／62.63%、72.68%／68.40%、73.11%／68.40%。筛选相对原生拟合的两项平均差为 −5.99 个百分点，母来源配对区间 [−13.63, −1.17]。 原生拟合选中 PARSE 分类与普通提案估值，在四份 B8 TRAIN 上平均增加 5.00 个百分点。四组均未检出该组合的新增反证，两项变更都缺少原文证实的修正见证。要求每项变更均有修正见证时，六种同预算双组均拒绝；仅按反证筛选时六种均可采纳该组合。  [固定 DEV 配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B8_SCREENED_FIXED_DEV_20261120.json)

## Revision 6 M1 MAUD 条款锚点见证

M1 从每条义务的锚点反查直接适用的疫情例外。九份原后批 TRAIN 的 45 个锚点都被模型填入肯定见证，两类契约的 18 项原始答案全为 Yes。应用相同原文核验后，新接口、固定字段、直接读法、前一有效关系接口分别为 13/18、13/18、12/18、17/18。相对直接读法的分类配对区间为 [0, +16.67] 个百分点。新增 9 笔，复用 36 笔，固定 DEV 沿用。 [配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_ANCHOR_WITNESS_TRAIN_20261120.json)

## Revision 6 M2 ContractNLI 按原条款作用域否决

复用五组已封存的比较和 12 份不同的后批 TRAIN 合同。限制否决的迁移范围后，B5 口头信息题从 8/9、正确类证据 F1 81.48% 恢复至 9/9、92.59%，与四个强对照持平。B4 两项分类增益均来自同一份超出对应作用域的 B5 合同。PARSE B4 的 B6–B8 回放中分类仍为 7/9，证据 F1 为 24.07%，四个强对照为 26.54%。固定 DEV 沿用，新增请求 0。 [五组比较与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SCOPED_VETO_TRAIN_20261120.json)

## Revision 6 M2 B5 普通提案的分类冲突筛选

同组池下，独立原文见证使候选驱动拒绝口头信息更新，四个对照采纳。后批八份由共用规则确定，唯一待解合同上提案优于进入程序。候选驱动为 8/9 对 9/9，正确类证据 F1 为 81.48% 对 92.59%。固定 DEV 沿用。 [拟合与后批配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B5_ASSERTION_SCREEN_TRAIN_20261120.json)

## Revision 6 ContractNLI 副本原文角色

共用原文核验后，固定 DEV 五臂各修正三项副本题且零退化。全量执行四内部臂分别为 211/272、证据 F1 57.67%，PARSE 为 202/272、50.52%。两份后批 TRAIN 的合成、固定、直接各为 2/2、1/2、1/2。两项配对区间下界为零，固定 DEV 对两种统摄写法覆盖为零。 [五库累计与后批配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_MENTION_ROLES_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 副本动作的授权关系

在三份早批原 TRAIN 上，合成、固定、直接分别为 2/3、0/3、1/3。锁定合成后，两份 B8 原 TRAIN 为 1/2、0/2、0/2，正确类证据 F1 为 25%、0%、0%。相对两强对照的分类配对区间下界均为零。五库累计 DEV 沿用，15 笔新读取均正常解码。 [锁定选型和后批结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_ACTION_TRAIN_20261120.json)

## Revision 6 ContractNLI 累计执行与副本授权

七个共用修订已合入同一固定 DEV 入口，五臂结果逐题复现此前累计表。新增共用副本授权核验覆盖原 TRAIN 和固定 DEV 各一份，五臂各修正一题。完整重算四内部臂 208/272、证据 F1 56.57%，PARSE 199/272、49.42%。 [运行入口](../experiments/convergence_revision6_cni_cumulative_dev.py) · [五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_APPROVAL_AND_FIXED_DEV_20261120.json)

## Revision 6 OpenExempt 宾州资产和部分有效读数

共用条文核验使固定 DEV 四内部臂分类／估值 F1 升至 86.03%／83.50%，PARSE 为 85.45%／79.26%，五臂零退化。B4 允许按方案使用有效读数后查到 PARSE 新增两项不适用分类引文，采纳决定持平。16 份原前向 TRAIN 上，候选驱动与同预算按时间、按分歧均为分类 69.95%、估值 56.90%。 [配对证据与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_PA_CIVILIAN_ASSETS_AND_FIXED_DEV_20261120.json)

## Revision 6 OpenExempt 俄勒冈个人财产估值

依据随题独立资产计分条件、原法条、单一申报人与明示产权，修正每件资产的豁免金额。固定 DEV 四内部臂估值 F1 达 80.66%，PARSE 达 77.62%，五臂均无退化。两批配对 TRAIN 里普通提案均未超越进入程序，新增收益归因于共用原文核验。 [八份配对 TRAIN 与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_OREGON_PROPERTY_AND_FIXED_DEV_20261120.json)

## Revision 6 MAUD 重复标记与节选覆盖

九份后批 TRAIN 的合成读器在保守合并重复标记后保持 17/18，固定字段和直接对照分别为 13/18 和 12/18。固定 DEV 四份有重复标记的合同均已答对两项契约题。剩余五项契约失分在四份合同中，分别涉及节选外的例外、可见范围与参考分歧或节选无疫情字样。累计五库结果沿用。 [真实归档回放与双视图定位](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_EXCERPT_PROVENANCE_20261120.json)

## Revision 6 ContractNLI 用途约束归因

两种原文句法覆盖原 TRAIN 3/24，分类和引用均符合原参考，固定 DEV 覆盖 0/16。仅统一引文时，候选驱动仍多答对一题。把用途分类也按原文统一后，原 B3 与 B5 两次过渡的五种选组各为 7/9，正确类证据 F1 各为 74.07%。B4 的协议事实与第三方披露比较独立保留。 [用途约束消融](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_PROOF_TRAIN_20261120.json)

B4 普通提案沿用原分流，后批九份协议事实题各为 7/9、证据 F1 74.07%。复用九笔采纳程序读数，另补两笔进入程序。B4 PARSE 的第三方披露后批使用九对原版响应，分类五路均为 7/9，正确类证据 F1 为 31.62% 对 26.54%，配对区间跨零。两项均未触发固定 DEV 扩验。 [B6–B8 普通提案](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_B4_LATER_TRAIN_20261120.json) · [B6–B8 PARSE 提案](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_PARSE_LATER_TRAIN_20261120.json)

## Revision 6 ContractNLI 按假设选组

B4 普通与 PARSE 提案的采纳差异在同一批三份 B5 合同上各修正一项。对四个同信息强对照，普通提案为 39/51 对 38/51，PARSE 为 40/51 对 39/51，两项分类区间下界都为零。B3 普通与 B5 PARSE 过渡按同一规则锁定，补三笔读数，六份后批合同的九道采纳相关题上为 7/9 对 6/9，正确类证据 F1 为 53.81% 对 59.26%。原五库固定 DEV 分数沿用。 [B4 普通提案](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_TRAIN_20261120.json) · [B4 PARSE 提案](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_PARSE_TRAIN_20261120.json) · [两个额外前向批次](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TASK_SCREEN_FORWARD_TRAIN_20261120.json)

## Revision 6 OpenExempt 择法与资产条款

B6 共用随题条文核验后，进入程序的分类 F1 为 63.49%，PARSE 为 72.01%。正差只见于亚利桑那与伊利诺伊，原 B7、B8 均无相关法域。四种同预算筛选采纳一致。固定 DEV 五臂剔除不适用的宾州缝纫机引文，四内部臂分类／估值 F1 为 84.93%／80.36%，PARSE 为 84.35%／76.65%，均零退化。 [原生评分与后批覆盖](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_CLAUSE_SCOPE_AND_FIXED_DEV_20261120.json)

## Revision 6 OpenExempt 逐任务候选与分类资产绑定

补齐四批 32 笔原 PARSE 响应，B6 的分类提升集中在训练拟合。资产名大小写统一后，B6 PARSE 分类 F1 由 70.97% 达到 72.01%，进入程序为 60.16%。候选驱动、时间、分歧和进入风险四种筛选均保留进入程序，纯原生拟合选择 PARSE 分类。固定 DEV 五臂各改善一份、零退化，累计四内部臂分类 F1 为 83.79%，PARSE 为 83.01%。共用核验解释这项固定 DEV 增益。 [候选池](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_REJECTED_PARSE_TRAIN_20261120.json) · [五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_EC_IDENTITY_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 协议事实的披露限制

前四批七份原 TRAIN 上，同输入合成、固定字段、直接分别答对 1/7、6/7、6/7，留一训练多数类为 6/7。合成对六份未提及的合同把其他保密义务当成协议事实的披露限制。21 笔冻结读数正常解码，拟合保留当前程序，五库累计固定 DEV 沿用。 [三路对照与症状](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_AGREEMENT_FACT_TRAIN_20261120.json)

## Revision 6 ContractNLI 强制披露通知的原文角色

把法定披露触发、编号通知义务和信息提供方绑定，覆盖原 TRAIN 2/24、固定 DEV 7/16。固定 DEV 五臂通知题各由 8/16 到 12/16，证据 F1 达 68.75%。早期覆盖保护也为 12/16，其普通教师和 PARSE 的证据 F1 分别为 39.58%、43.75%。本次为共用修订。累计 ContractNLI 内部臂 207/272、证据 F1 56.57%，PARSE 198/272、49.05%。复用 18 笔原响应，新增 0。 [原文取证、强对照和五库结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_NOTICE_ROLES_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 ContractNLI 引文选组

在 B1 普通提案、B4 PARSE 提案及其已归档前向上去重复用 39 笔原 TRAIN 响应。每个筛选策略同预算核验一组。B4 候选驱动发现四项有源文证据的退化并保留进入程序，B5 正确类证据 F1 为 50.06%，同信息按时间和分歧为 47.71%，完整前缀原生对照同为 50.06%。各为 39/51。B1 筛选均采纳提案，后两批为 66/102，进入程序为 76/102。五库累计 DEV 沿用。 [原候选和后批对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_ARCHIVE_GROUP_GUARD_TRAIN_20261120.json)

## Revision 6 M1 MAUD 条件与稀疏见证

显式条件与每类义务的首个见证在原九份后批 TRAIN 上得到 9 笔真实读数。共用原文核验后，修订接口、固定字段、直接读法及前一去重联合接口依次为 13/18、13/18、12/18、17/18。四处退化来自两份仅负面节选有疫情标记的合同。相同结构在固定 DEV 的覆盖为 0/16，累计分数沿用。 [配对原生结果与退化证据](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_WITNESS_TRAIN_20261120.json)

## Revision 6 M1 MAUD 限制清单锚点

在固定 DEV 的 4/16 份合同上各恢复一个限制清单锚点。三路同用完整节选、同一锚点清单和共用范围规则。联合编码、固定字段、直接读法分别答对 2/8、6/8、5/8。联合编码在三份合同上排除了全部标记与两类义务的关系，三个普通经营题失分。12 笔新执行器读数全部正常解码。联合枚举留在开发比较，五库固定 DEV 累计表沿用。 [配对结果与失败归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_GOVERNOR_DEV_20261120.json)

## Revision 6 M2 OpenExempt B8 候选池

复用四份原 B8 TRAIN 上五个实际程序的 40 笔归档响应。以相同的原文、执行器设置、原生评分和双组预算比较 25 种分类／估值组合。住宅豁免原文核验覆盖 1/4 份 TRAIN 和 0/16 份固定 DEV。核验后四种筛选策略均保留 M2 的进入程序。纯原生拟合采用 PARSE 分类和普通估值，当批两任务平均 F1 高 5.00 个百分点。累计固定 DEV 沿用，新增模型请求 0。 [B8 选组、采纳及累计 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B8_PORTFOLIO_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 OpenExempt B1 家庭用品选组

对 B1 进入程序、普通提案及实际采纳的 PARSE 提案共用伊利诺伊州家庭用品作用域核验。普通提案仅替换估值的两任务平均原生增量由 +4.17 个百分点降为 0，候选驱动、按时间、按答案分歧及原生拟合均保留进入程序。原 B2 四份后批的历史进入程序分类／估值 F1 为 55.06%／33.33%，历史 PARSE 为 57.14%／25.00%。已阅固定 DEV 中，四内部臂分类／估值升至 83.27%／79.13%，PARSE 升至 82.49%／75.45%，五臂无退化。复用 46 笔，新增 0。 [候选池、原生比较与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_B1_HOUSEHOLD_FIT_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 MAUD 重复条款锚点

对同一有效条款锚点只解码一次，保留另一契约范围的未决状态。将同一规则用于两种锚点接口后，新接口在三份原 TRAIN 恢复普通经营判定，原始得分由 8/18 升至 11/18，旧锚点保持 11/18。共用条款核验已覆盖这三处，新接口与固定、直接强对照仍为 17/18、13/18、12/18。原 24 份 TRAIN 中，疫情线索仅出现在负面契约节选的三份均已用于比较；固定 DEV 16 份无同类输入。复用 18 笔原响应，新增 0。 [解码回放及可用来源](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_ANCHOR_IDEMPOTENCE_TRAIN_20261120.json)

## Revision 6 M1 MAUD 条件与义务的局部关系

合成接口从原消费者导出条件和受约束义务的联合读数，保留 100 个局部状态的输出和未知含义。原 B5–B8 完整适用组为 9 份 TRAIN。无额外源文核验时，新接口、固定和直接分别正确 8/18、10/18、9/18。三路均用既有范围核验，再分别定位同一公司的两个疫情前导条款后，为 17/18、13/18、12/18，旧锚点合成为 14/18。两处明确的单项负面契约例外与原 No 标签有分歧，搁置两项计分的敏感性分析分别为 15/16、13/16、12/16、14/16。两条强对照的母来源配对 95% 区间下界均为零。新增 9 笔、42,217 tokens，复用 27 笔，固定 DEV 沿用。 [完整原生评分和敏感性分析](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_OPERATIVE_EDGES_TRAIN_20261120.json)

## Revision 6 OpenExempt 机动车估值条款

将单一申报人的联邦额度绑定到题面第 522(d)(2) 项，并用其他资产价值的保守上界核算威斯康星州剩余额度。原 TRAIN 覆盖 1/32，固定 DEV 覆盖 4/16，六个核验金额均符合原评分参考。已阅固定 DEV 的估值 F1，四个内部臂由 76.59% 升至 78.61%，PARSE 由 73.30% 升至 74.93%，各改善 3 份和 2 份，零退化。B2 两个程序原本都报对该联邦金额，候选驱动、按时间和答案分歧均保留进入程序。复用 21 笔原读数，新增 0。 [估值、采纳及五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_MOTOR_VEHICLE_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 外部顾问许可

把明确的外部专业顾问定义连到接收方的访问许可，并区分同一条中的必要知悉许可和其他第三方的事前同意。原 TRAIN 覆盖 2/24，固定 DEV 覆盖 1/16。B3 提案在该题由 4/9 到 6/9，与进入程序同分；证据 F1 为 38.89% 对 43.33%。固定 DEV 四个内部臂该题各由 10/16 到 11/16，PARSE 由 9/16 到 10/16。五臂均无分类或引文退化。五库累计中，ContractNLI 内部臂为 203/272、证据 F1 54.61%，PARSE 为 194/272、证据 F1 46.97%。这是已阅 DEV 上的共用修订。复用 20 笔原响应，新增 0。 [源绑定与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EXTERNAL_RECIPIENTS_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 MAUD 八批候选对照

对原 24 份 TRAIN 的 16 项普通教师和 PARSE 提案逐笔回放，复用 84 笔候选与进入程序读数及 6 笔 B4 无损恢复读数。5 项原有正增益经共用输出恢复和可见条款核验后剩 3 项，另有 1 项退化。剩余 4 项差异均为普通经营题，给两边同样的已审 TRAIN 母合同范围后逐项同判。八批正式 M2 与普通教师的 MAUD 程序哈希逐批一致。新增负面契约规则核实 B1 一项明确疫情例外并定位原 PARSE 退化，固定 DEV 覆盖 0/16，原指标沿用。新增请求 0。 [逐批原生计分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_CANDIDATE_ARCHIVE_TRAIN_20261120.json)

## Revision 6 M1 ContractNLI 具名事件关系与引文归因

同一全文和锚点下，用具名关系分别表达条款绑定、事件不符和未决。三份 TRAIN 的六个旧未决判断均给出了原生分类，合成原始分数由 3/9 到 5/9，固定、直接各 7/9。新增三笔、29,901 tokens，九笔旧读数复用。应用已有共用规则后三路均为 7/9，合成证据 F1 的 6.67 个百分点优势来自一份合同的存续引文，配对区间 [0, +20]。将同一原文规则用于三路，删除该存续证据中的既有请求权、保留义务与继受条款，并核对另一合同的请求专属触发。三路预测随后逐项一致，各 8/9，正确类证据 F1 各 74.07%。五臂固定 DEV 均无输出改动。 [三笔实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_RELATION_TRAIN_20261120.json) · [引文归因回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_RESIDUAL_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 事件链接与保留例外

同一全文及锚点索引下，新事件接口、固定字段和直接读法在三份早批 TRAIN 上分别答对 3/9、7/9、7/9。合成接口在两份合同的六个任务均输出未决关系，九笔正常解码，共 87,637 tokens。之后用相同原文规则核实交易终止触发和保留例外，合成得分回放为 6/9，双对照各 7/9，正确类证据 F1 为 55.56% 对 56.30%。固定 DEV 的三处保留例外均已答对，最小引文修订把 PARSE 该题证据 F1 从 23.45% 提到 29.70%，四内部臂保持 66.00%，零退化。累计 PARSE 证据 F1 为 46.60%。 [原始三路实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_WITNESS_TRAIN_20261120.json) · [共用原文回放与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVENT_LINKAGE_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 OpenExempt 冲突方向与选组

将跨任务冲突绑定到该任务自己的产权和条款资格条件。B7 原两条冲突中，车辆引文有独立原文证据足以归为估值误引，家庭用品引文的方向保留未决。两组预算下，B2 和 B3 的候选驱动策略更换所选组，六批的程序采纳沿用。16 份前向 TRAIN 上，候选驱动、按时间、按答案分歧及无方向归因消融的原生预测一致，分类／估值 F1 为 66.01%／54.54%。B2 和 B5 均保留进入程序。168 笔物理响应去重复用，新增 0。 [六批筛选与原生结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_SIGNED_DIRECTION_TRAIN_20261120.json)

## Revision 6 OpenExempt 资产类别与 B7 归因

共用核验识别带修饰语的独立物件，按题面法条去除宾州服装与缝纫机误引，为产权明确的服装和一项低于联邦单项上限的家庭用品补引。固定 DEV 四个内部臂的分类 F1 从 81.44% 升至 81.88%，估值为 76.59%。PARSE 从 81.35%／73.01% 升至 81.80%／73.30%，五臂零退化。相同核验用于全部 B7 选组对照后，16 份前向 TRAIN 的分类与估值 F1 均为 66.01%／54.54%，引文多重集逐源一致。B7 两个跨任务冲突中，一个新增估值引文在原 EC、EV 参考均存在，另一个在两份参考均缺席。 [五库累计、原生配对与归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_ITEM_CATEGORIES_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 OpenExempt 同任务候选选组

两个组选出可由原文证实修正的估值候选，并检查原生拟合更高的同任务提案是否引入跨任务冲突。B7 检出两处新冲突，改采纳 PARSE 估值程序。按时间与按答案分歧均采纳普通教师的估值程序。16 份前向 TRAIN 的分类 F1 各为 64.98%，估值 F1 为 52.34% 对 53.73%。两项平均差 −0.69 个百分点，95% 配对区间 [−1.85, 0]。B7 后续四份的估值 F1 为 48.99% 对 54.52%。复用 144 笔，固定 DEV 沿用。 [同预算选组及原生结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_COMPETING_PORT_TRAIN_20261120.json)

## Revision 6 MAUD 负面契约的引文范围

在 24 份原 TRAIN 和 16 份公开 DEV 输入上检查肯定引文的位置，复用 70 笔实测响应。B6 第三份的普通经营例外未被负面契约的编号列表引入，借款和资本支出例外出现在另一题节选的后文。四路均将这份的负面题改为未决，三份前向合同的该题仍各为 0/3。B6 第二份的贷款修改和 B8 第二份的临时关闭确有可见单项例外，原参考均为 No。普通经营及配对区间沿用，16 份 DEV 无本次范围变动。 [来源范围和原生回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_NEGATIVE_WITNESS_TRAIN_20261120.json)

## Revision 6 MAUD 联合字段的前向 TRAIN

按公共输入锁定后四批里仅一侧有疫情线索且既有规则未解决两项的三个合同。复用九笔同输入对照，新增三笔联合字段读数、21,183 tokens。普通经营联合 3/3、固定 1/3、直接 0/3、旧锚点合成 2/3，四路负面契约均为 0/3。两任务合计联合较固定净增两项，95% 配对区间 [0, +50] 个百分点，固定 DEV 沿用。三处负面误判的肯定锚点分别是贷款修改、借款以及分行临时关闭的单项例外。 [原生配对与运行用量](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_JOINT_FORWARD_TRAIN_20261120.json)

## Revision 6 MAUD 联合范围的同信息归因

将已有子节、前导条件、显式引用规则同时给 B1–B4 四路实测。联合字段 19/20，固定字段 17/20，直接 16/20，旧合成 14/20。联合对固定和直接分别净增两项和三项，母来源配对区间下界均为零。两处相对双对照的修正经原 TRAIN 母合同确认，分别是独立负面前导以及从普通经营到负面条款的单向引用。母合同只用于归因。复用 40 笔。 [同信息配对及归因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_JOINT_SCOPE_CONTROLS_TRAIN_20261120.json)

## Revision 6 ContractNLI 用途限制的跨条款证据

按同名用途连接限制与许可例外，按同一披露方和接收方连接相邻条款的所指信息。共用链接覆盖原 TRAIN 3/24，直接、固定、合成分别修正 3、2、1 份证据，零退化。沿用已排除未勾选选项的归因口径，双读器与两个强对照仍各为 23/24，正确类证据 F1 为 84.58% 对 83.19%，配对差 +1.39 个百分点，区间 [−4.86, +7.64]。固定 DEV 公共输入覆盖 0/16。复用 72 笔实测，新增 0。 [TRAIN 跨条款比较](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_LINKS_TRAIN_20261120.json)

## Revision 6 M1 ContractNLI 未勾选条款的来源归因

B5 第三份合同中，合成读器实际把未勾选的单向协议选项读为已生效的非授予条款，归档参考也只引该选项。这是双读器唯一额外命中的权利分类。保留历史原生分数。仅在归因敏感性分析中搁置这项无生效依据的判断后，双读器与两个强对照均为 23/24，正确类证据 F1 为 80.77% 对 78.19%，配对区间 [−5.56, +10.42] 个百分点。复合用途规则的对照为 83.75% 对 79.58%，区间 [−2.78, +11.11]。匹配原 TRAIN 1/24、固定 DEV 0/16。复用 72 笔实测，新增 0。 [来源归因与独立敏感性结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_FORM_ATTRIBUTION_TRAIN_20261120.json)

## Revision 6 M2 ContractNLI B4 按假设采纳

在已有 B4 披露角色组选择之后，补齐整份候选与分假设采纳的原生比较。按 B1–B4 拟合保留整份、逐假设和同一两项角色范围的原生得分对照。原 B5 三份合同的 51 项分类各为 35/51。候选驱动与同范围原生选型逐项相同，证据 F1 均为 32.35%。按时间与按答案分歧为 29.41%，逐假设原生选型为 34.31%，整份采纳为 39.54%。复用 30 笔实测响应，新增 0，固定 DEV 沿用。 [全任务及角色范围对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_SCOPED_ADOPTION_TRAIN_20261120.json)

## Revision 6 OpenExempt 亚利桑那家庭用品与 B2 选组

在原输入的同一亚利桑那条文、已确定产权和估值下核对家庭用品，排除不适用的服装、牲畜、戒指和宠物引文。B2 估值候选相对进入程序的 F1 差从 +25.00 个百分点降至 0，候选驱动、按时间和按答案分歧均保留进入程序。四内部臂固定 DEV 分类 F1 从 80.74% 到 81.44%，估值从 74.85% 到 76.59%；PARSE 分别从 79.27% 到 81.35% 和 72.31% 到 73.01%。五臂各一份母来源改善，零退化。DEV 的估值增益来自去除不适用引文，未增加产权未决的资产主张。复用 16 笔 TRAIN、4 笔固定 DEV，新增 0。 [B2 选组及五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_ARIZONA_HOUSEHOLD_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 复合条款的用途证据

在已引用完整用途限制时，区分附带披露、复制、留存和保密存续义务，保留已核实的跨条款证据。共用规则在 24 份原 TRAIN 上分别修复合成两份、固定和直接各一份，零退化。旧双读器比较的正确类证据 F1 复算为 M1 86.53%、两条强对照各 79.58%，差的配对区间 [−1.39, +15.28] 个百分点。此规则源于同批错误，复算属于开发诊断。固定 B8 DEV 16 份、五臂均无触发，累计五库指标沿用。合成臂唯一额外正确的权利分类已复核，单独直接实答 Contradiction，固定字段匹配臂为未决。新增请求 0。 [TRAIN、请求复核和固定 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COMPOUND_PURPOSE_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 ContractNLI 双读器联合选择

在原 B1–B4 按任务和两读器分类是否一致拟合决策，固定原文证明后应用到 B5–B8。直接加合成与直接加固定字段分别答对 24/24 和 23/24，单独直接也为 23/24。两条强对照正确类证据 F1 均为 78.19%，M1 为 83.55%，差 +5.36 个百分点，95% 配对区间 [−4.07, +14.58]。13 项待解任务上为 13/13 对 12/13，证据差 +9.89 个百分点，区间 [−7.34, +25.76]。合成臂改变七项待解输出，其中两份合同的用途证据因附带条款而退化。72 笔原 TRAIN 读数复用，新增 0，固定 DEV 沿用。 [双读器 TRAIN 与五库累计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_EVIDENCE_PAIR_TRAIN_20261120.json)

## Revision 6 ContractNLI 第三方取得证据链

核对独立第三方取得、合法来源限定及支配该分项的保密例外。原 TRAIN 覆盖 15/24，固定 DEV 覆盖 3/16，分类参考均一致。固定 DEV 五臂各三份原文证据改善、零退化，分类仍各 13/16。该题证据 F1 四内部臂从 15.63% 到 33.13%，PARSE 从 13.54% 到 26.88%。累计 272 项的 ContractNLI 证据 F1 从 53.21% 到 54.24%、45.45% 到 46.23%。同规则下，12 份三路实测的取得题合成、固定、直接为 9/12、9/12、10/12。复用归档，新增 0，收益来自共用原文核对。 [TRAIN、固定 DEV 与累计原生指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_INDEPENDENT_RECEIPT_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 OpenExempt 分类与估值组合选组

在 B3、B4、B6、B7 四个已有精确前向读数的过渡上，允许各策略从同一批实际读器分别选择分类和估值。每个筛查策略选两组，逐任务要求可证修正，并用实测组合检查新增冲突。候选驱动、按时间、按分歧均只在 B7 采纳估值，前向 16 份 TRAIN 的分类、估值 F1 同为 64.98%、53.73%。相对只按原生拟合，两项平均差 +5.21 个百分点，95% 配对区间 [+1.27, +10.10]。相对不更新，平均差 +0.43 个百分点，配对区间跨零。正向差异来自共用筛查条件，候选驱动与两条同预算强对照逐预测相同。复核 144 笔归档响应，新增 0。 [选组、组合与前向评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_PORTFOLIO_TRAIN_20261120.json)

## Revision 6 M1 ContractNLI 第三方转移的定向证据

保留同一批 12 份 TRAIN 合同及三个例子的文本与标签，移除例子编号，并分别读取对外披露与独立取得的许可和限制。合成、固定和直接分别答对 7/24、15/24、6/24，正确类证据 F1 为 23.21%、20.10%、20.63%。两个归档整文读器各为 18/24。合成的 12 份披露许可均为已核查缺失，固定找到 10 份锚点。合成与固定的分类差为 −33.33 个百分点，两条同信息证据差的 95% 区间均含零。36 笔正常结算、213,353 tokens，固定 DEV 沿用。 [定向证据配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_TRANSFER_WITNESSES_TRAIN_20261120.json)

## Revision 6 M1 ContractNLI 第三方信息转移方向

用三份 B1–B4 原 TRAIN 例子注册读者，在 B5–B8 全部 12 份原 TRAIN 比较对外披露与从独立第三方取得。三路共用原文、索引与例子。定向关系字段从三项减到两项，27 个有限状态解码等价。合成、固定和直接分别正确 1/24、3/24、12/24，正确类证据 F1 为 4.17%、12.50%、26.54%。两个归档整文读器各为 18/24。结构化原响应均成功解码，但全部转移记录没有肯定的许可或禁止判断。新增 36 笔，223,768 tokens，固定 DEV 沿用。 [原生配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DIRECTED_TRANSFER_TRAIN_20261120.json)

## Revision 6 MAUD 例外条款的选择性引用

按原文核对负面契约引用的例外编号。24 份原 TRAIN 中覆盖一份。该合同普通经营款的疫情条件位于第 (ii) 项，负面契约明确只引用 (i)、(iii)、(iv)、(v)。合成与固定读器均以被排除的第 (ii) 项作肯定依据，直接读器引用了后续的举债条目。排除一项引用只能约束前导条件，无法确定其他条款是否另有例外。固定 DEV 16 份中覆盖一份，其负面契约按区间引入 (w) 至 (z)，包括疫情条件 (y)。五臂原本均已答对，仍为各 13/16。复用五笔响应，新增 0。 [作用域证明与原生评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_SELECTIVE_IMPORT_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 OpenExempt 多提案反证选组

在 B4 和 B7 两个已有完整下一批读数的过渡上，联合比较原普通教师和 PARSE 提案。各策略共用三个读器、同一源文规则及每组选定的六笔读数。候选驱动优先选能排除原生分领先提案的组，所有策略用同一筛查门槛。B4 均保留进入读器。B7 候选驱动选中新增两处跨任务冲突的组并保留进入读器，按时间和原生拟合采纳普通提案。八份后续 TRAIN 上，候选驱动的分类 F1 为 63.54%，估值 F1 为 65.12%，按时间及原生拟合为 56.15% 和 66.85%。两项均值差的 95% 配对区间为 [−1.25, +8.71] 个百分点。候选驱动与答案分歧、现行程序风险选组的预测完全一致，固定 DEV 沿用。核对 120 笔归档请求，新增 0。 [同预算选组与前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_CANDIDATE_GROUP_TRAIN_20261120.json)

## Revision 6 ContractNLI 用途限制证据范围

实现用途证据的来源核验，仅在已引用独立、完整的限制条款时删去可识别的辅助文字。三臂复用全部 24 份 TRAIN 的 72 笔归档请求，并在已结算的七份单题合同上复算。投影 M1 的用途题正确类证据 F1 从 69.32% 到 73.13%，同信息匹配对照从 85.71% 到 90.48%。三路索引读数中，固定和直接各改善一份，合成无变化。固定 B8 DEV 的 16 份合同在五臂均未触发删除。新增请求 0，未达到修订发布或 M1 扩验条件。 [TRAIN 与固定 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PURPOSE_SUPPORT_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 ContractNLI 单题读法与标签澄清

沿用 B1–B4 选型，在 B5–B8 的七份仅一题待解的原 TRAIN 合同上，用同一全文和原文证明比较单题读法。首轮 14 笔请求中，M1、固定加直接匹配对照、直接读法分别答对 7/7、3/7、1/7。直接提示的相对顺序表述出现六处相反标签。随后只补七笔明确写出正反标签各自含义的直接读取，保留合成和固定读数。待解题正确数分别为 7/7、7/7、5/7，归档双题直接读法为 7/7。按全部 14 题计算，四路正确类证据 F1 分别为 78.71%、86.90%、72.62%、83.33%。M1 对匹配对照的待解题证据 F1 差为 −16.39 个百分点，配对 95% 区间 [−34.69, +4.76]。两轮共新增 21 笔、108,708 tokens，未达到固定 DEV 扩验门槛。 [首轮单题实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PROJECTED_READ_TRAIN_20261120.json) · [标签明确后的强对照](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_PROJECTED_DIRECT_TRAIN_20261120.json)

## Revision 6 M1 ContractNLI 按待解任务选读器

区分由原文证明的任务与仍需读器的任务。在 B1–B4 各任务的未解样本上拟合读器分数，B5–B8 按待解任务选一路。12 份前向合同的 24 项中，11 项可共用原文证明，两份合同的双任务均可直接作答。M1、同信息固定加直接选型、直接读器分类为 23/24、22/24、23/24，正确类证据 F1 为 79.73%、75.00%、76.81%。旧 M1 路由共用同一证明后的分数为 75.84%。M1 对前两条强对照的证据差区间分别为 [−4.77, +14.11] 和 [−5.26, +10.76] 个百分点。复用 72 笔响应，新增 0，未触发固定 DEV 扩验。 [前向选型与配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RESIDUAL_ROUTING_TRAIN_20261120.json)

## Revision 6 ContractNLI 员工披露证据链补全

从模型已引用的许可条款出发，补入能够按编号或定义唯一核实的前导义务及员工成员定义。将其他受领人的事前批准条件留在其自己的义务范围。原 TRAIN 覆盖 2/24，原固定 DEV 覆盖 5/16。五臂各两份证据改善、零退化，分类均为 13/16。员工披露证据 F1 由四个内部臂 61.27% 到 65.15%，PARSE 49.36% 到 52.50%。全部 272 项证据 F1 分别为 53.21% 和 45.45%。单题配对中，M1 和同信息直接读法的证据 F1 为 67.33% 和 80.00%，分类均为 5/5。提升来自共同原文核验。复用配对响应 15 笔，另核对固定 DEV 4 笔，新增 0。 [证据链与五库累计结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RECIPIENT_EVIDENCE_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 B4 ContractNLI 角色组前向

复用真实 B4 普通教师提案。B1–B4 的 12 份原 TRAIN 合同经共用规则后，进入和提案累计分类为 13/24、16/24。三种策略共用三组完整角色证据与原响应，各筛两笔。候选驱动选 B2 第一组并采纳提案，按时间及答案分歧选 B4 第三组并保留进入读器。原 B5 前向的三个合同中，四路各答对 5/6。候选驱动相对按时间及答案分歧的正确类证据 F1 为 55.56% 对 30.56%，配对 95% 区间 [−25.00, +100.00] 个百分点。只按 TRAIN 原生分数选出的程序与候选驱动相同。复用 27 笔，新增 3 笔、33,899 tokens，无教师调用，未触发 DEV 扩验。 [选组与 B5 原生结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B4_RECIPIENT_SELECTION_TRAIN_20261120.json)

## Revision 6 OpenExempt 伊利诺伊误引与 B5 选组

用原题法条和资产核验非独立授予的节标题、明确不适用的机动车、职业工具和医疗辅助器材引文。原 TRAIN 和固定 DEV 分别覆盖 8/32、3/16 个母来源，对每项任务核验 45、10 个资产与引文位置，均无原参考冲突。B5 最早组的候选分类、估值 F1 原高 18.25、22.22 个百分点，共用规则后差值均为零。两种选组仍保留进入程序。固定 DEV 四个内部臂分类从 79.63% 到 80.74%，估值从 74.50% 到 74.85%；PARSE 分类 78.92% 到 79.27%，估值 72.31%。相关各项各修正一份，所有臂零退化。复用 16 笔 B5 与 3 笔固定 DEV，新增 0。 [B5 与五库累计原生结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_ILLINOIS_ELIGIBILITY_AND_FIXED_DEV_20261120.json)

## Revision 6 MAUD 相邻款各自前导条件

实现款号与引用核验，疫情前导条件只约束其所在普通经营款。负面契约若有自己的完整前导段，且没有明确引用前款条件，则保持两款的作用域分离。原 MAUD TRAIN 覆盖 3/24，均与原参考一致。三路已有读数覆盖其中两份，合成、固定和直接各修正两题，分别由 12/18、11/18、10/18 到 14/18、13/18、12/18。负面契约三路均为 6/9，合成的剩余差异出现在普通经营。两项配对区间下界均为零。固定 DEV 覆盖 0/16，复用 27 笔原响应，新增 0。 [同信息 TRAIN 比较](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_BRANCH_PREAMBLE_TRAIN_20261120.json)

## Revision 6 M2 补齐 B2 和 B5 当批筛选

两批原先均没有候选程序的精确下一批读数。本轮验证 **32 笔已有响应**，用共同规则重建两批各四份 TRAIN 的同信息筛选。B2 估值候选的当批 F1 高 25.00 个百分点，收益集中于最新组，两种选组都选该组，均因缺少已验证修正而保留进入程序。B5 分类和估值候选分别低 9.19 和 28.82 个百分点，三组有完整读数，两种选组同样保留进入程序。两个当批拟合均已持久化，新增请求 0，没有启动此前缺失的前向实验。 [两批筛选和入库结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_MISSING_FORWARD_FIT_TRAIN_20261120.json)

## Revision 6 ContractNLI 共用非授予条款核验

单次读取双任务的归档原响应暴露两类漏判。一份合同的固定字段把非授予条款和术语定义分配给不同锚点，另一份只读到标题。共用核验把非授予结论绑定到相应正文，并在有业务用途例外时另要求相邻的明确知识产权非授予条款。原 TRAIN 支持 5/24，五份均与参考一致。后四批中 M1 和匹配对照的权利题各由 8/12 提至 10/12，归档直接保持 11/12。两任务合计正确类证据 F1 分别为 76.11%、73.61%、74.03%，M1 对两条对照的配对下界均不大于零。固定 DEV 覆盖 1/16，五臂原生预测均不变，新增请求 0。 [TRAIN 与固定 DEV 共用核验](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_RIGHTS_SCOPE_TRAIN_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 ContractNLI 前向读器选择

按原 B1–B4 学习读器选择，再在原 B5–B8 的 12 份 TRAIN 合同前向比较。按合同选一路时，M1、同信息匹配对照、归档直接读器分别答对 23/24、22/24、23/24，正确类证据 F1 为 71.62%、68.97%、70.69%。复用 72 笔归档请求。随后在一次合同读取内分别指定用途限制和未授予权利的读法，17 笔新请求结算，七份合同共用响应，五份读法有差异。M1、匹配对照、归档直接分别为 20/24、20/24、23/24，证据 F1 为 68.61%、66.11%、70.69%。M1 相对匹配对照的 +2.50 个百分点配对区间为 [0, +7.50]，权利任务两路各 8/12，归档直接为 11/12。两轮均未触发 DEV 扩验。 [按合同选择](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_FORWARD_ROUTING_TRAIN_20261120.json) · [单次读取双任务](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_MIXED_ROUTING_TRAIN_20261120.json)

## Revision 6 M2 共用规则后的采纳门槛

对四次原 OpenExempt 过渡，先用同一套公开规则处理每路 TRAIN，再比较提案的剩余收益。B6 只换分类的 TRAIN 两任务平均增量从 +0.69 变为 −2.46 个百分点，因此保留原分类。16 份原前向 TRAIN 的分类 F1 从 61.78% 到 62.80%，估值 F1 保持 51.65%。按时间选组与候选驱动逐批同判。相对不更新，两任务平均差 +0.43 个百分点，配对区间 [−1.03, +2.10]。复用 112 笔原响应，新增 0。 [门槛与前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_RESIDUAL_ACQUISITION_TRAIN_20261120.json)

## Revision 6 Airline 巴拿马线路

原公开规则表的巴拿马至美国费率接入共用行李费用计算。用 24 份原 TRAIN 行李清单构造两个方向、六舱位的 288 个规则核对，均与封存基准计算一致。固定 DEV 一份适用，五臂总费用正确数各 15/16→16/16，均无退化。两种分配算法同价，收益归于共用规则。 [线路回放与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_AIRLINE_PANAMA_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 ContractNLI 制作义务证据链

复用 33 笔原 TRAIN 响应，同一原文规则把已引制作条款连到实际前导义务，并移除其他动作的引文。合成、固定、直接的正确类证据 F1 为 65.28%、60.89%、73.23%，分类正确数仍为 16/22、15/22、17/22。合成相对直接差 −7.95 个百分点，配对区间 [−21.59, +2.27]。固定 DEV 一份有明确证据链，五臂已有相同引文。 [证据链回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_EVIDENCE_CLOSURE_TRAIN_20261120.json)

## Revision 6 M1 ContractNLI 副本制作与处置后留存

11 份原 B5–B8 TRAIN 合同的三路实测共 33 笔。加入同一套制作和留存规则后，合成、固定、直接各为 12/22、11/22、13/22。共同全量处置核查再修正每臂 4 项留存判断，三臂无退化，最终为 16/22、15/22、17/22。只计正确分类的证据 F1 为 49.47%、51.20%、70.96%。处置规则覆盖固定 DEV 0/16。候选保留在 TRAIN 库快照，尚未启用。 [三臂实测](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_LIFECYCLE_TRAIN_20261120.json) · [全量处置回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_COPY_DISPOSITION_READBACK_TRAIN_20261120.json)

## Revision 6 M2 OpenExempt 分任务采纳

复用 B3、B4、B6、B7 四次过渡的 112 笔实测响应。B7 两项分类与估值看似一致的变化实际把洗碗机和路由器归入服装。加入原文类别证据后，B7 只有估值通过分任务采纳，分类继续使用进入程序。统一类别与金额对照后，16 个原前向 TRAIN 的候选驱动及按时间路径均为分类 F1 61.78%、估值 F1 51.65%。只按训练分数选路线为 54.13%、51.65%，两任务平均差 +3.83 个百分点，配对区间 [+0.89, +7.47]。两种选组策略的采纳决定完全一致。新增请求 0。 [分任务前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_PORT_ACQUISITION_TRAIN_20261120.json)

## Revision 6 M1 MAUD 条款锚点与同信息核查

在原 B5–B8 的 9 份 MAUD TRAIN 合同上，合成接口、固定锚点、直接读器分别答对 11/18、10/18、9/18，合成的普通经营为 8/9。相对固定和直接的配对区间分别为 [0, +16.67] 和 [0, +27.78] 个百分点。新增冻结执行器请求 27 笔。原 24 份 TRAIN 中两份合同明示疫情例外只修饰自己的普通经营款。回放以同一规则修正三臂各 1 题，结果分别为 12/18、11/18、10/18。固定 DEV 原文覆盖 0/16，无新增读数。 [三臂配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_CLAUSE_ANCHORS_TRAIN_20261120.json) · [同信息回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_SUBSECTION_READBACK_TRAIN_20261120.json)

## Revision 6 M2 四次逐批前向选组

复用 B3、B4、B6、B7 的 56 笔物理响应，三组比较各次均与候选驱动共用组池、提案和每组两笔读数。候选驱动只把同一已答主张被改到公开额度以内计为修正。B7 候选驱动及按时间选组采纳提案，答案分歧及进入程序风险选组保留原程序。统一额度对照后，四次原下一批合计 16 母来源的估值 F1 分别为 24.79%、24.79%、23.85%、23.85%。候选驱动相对答案分歧的配对 95% 区间为 −1.98 至 +4.27 个百分点。新增请求 0。 [逐批选组和原生前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_FORWARD_ACQUISITION_TRAIN_20261120.json)

## Revision 6 M2 联邦单项额度与前向估值

B7 原 TRAIN 两个共同申报金额均支持基准的单项额度口径。候选驱动、答案分歧、按时间三种选组各复用两笔已测估值，均选择 B7-3 并采纳同一提案。该提案在 B8 唯一同范围高值资产报 980 美元，原参考为 700 美元。基于原题校准的共用检查将固定 DEV 四个内部臂估值 F1 从 72.82% 提至 74.50%，PARSE 从 70.58% 提至 72.31%，五臂各改善 3 份、无退化。新增请求 0。 [选组、前向对照与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_OE_JOINT_ITEM_CAP_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 用途限制的同信息引文对照

在原 24 份 TRAIN 上复用 72 笔响应，三路共用原文引文校验，保留任何可独立支持用途限制的引文。合成、固定分栏、直接读器的正确类证据 F1 为 70.70%、56.12%、61.94%。合成较固定分栏高 14.58 个百分点，配对 95% 区间为 +4.86 至 +25.99。较直接高 8.76 个百分点，区间为 −4.37 至 +22.64，确认组内差为 +1.15。固定 B8 DEV 五臂均无引文改写。新增请求 0。 [配对结果与五库既有 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_INDEXED_EVIDENCE_CONTROL_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 同条款索引接口

用途限制和未授予权利共用一套原文索引。先在 11 份原 TRAIN 比较合成、固定分栏和直接作答，再锁定接口，在其余 13 份原 TRAIN 确认用途限制。确认组该题三路分别正确 10/13、10/13、11/13，正确类证据 F1 为 64.49%、55.40%、57.84%，两项配对区间均包含零。原 TRAIN 全部 24 份合计两题三路为 37/48、37/48、35/48，正确类证据 F1 为 64.83%、55.85%、52.65%。两个阶段新增 72 笔，均正常生成。确认组未达到扩大到固定 DEV 的条件。 [首组 TRAIN](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_INDEXED_EFFECTS_TRAIN_20261120.json) · [确认组 TRAIN](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_INDEXED_EFFECTS_CONFIRMATION_TRAIN_20261120.json)

## Revision 6 OpenExempt 伊利诺伊州逐资产估值

B6 提案在两件产权明确的资产上补出通配豁免分类。对应估值一项报零、一项漏报。题面要求逐资产、逐法条计算。共用规则在原 TRAIN 覆盖 6 份母来源、14 件资产，金额均符合原参考。固定 DEV 覆盖 2 份、5 件，四个内部臂估值 F1 从 68.48% 到 72.82%，PARSE 从 66.24% 到 70.58%。五臂各改善两份、无退化。B6 提案未产生可接入估值的金额。新增请求 0。 [B6 提案与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_ILLINOIS_PAIR_AMOUNTS_AND_FIXED_DEV_20261120.json)

## Revision 6 B5 答案分歧强对照与开发定义修订

B5 在同一组池、同一预算下，候选驱动选 B1-1，答案分歧选 B4-0，均保留同一进入读器。两路在固定 DEV 的所有预测一致。原 TRAIN 中保密信息定义包含开发计划，固定 DEV 中受保护数据定义包含已开发的数据。两处的「开发」均用于界定受保护信息。共同修订使固定 B8 五臂该题各由 15/16 到 16/16，累计四个内部臂 202/272、PARSE 193/272。B5 候选驱动、答案分歧和按时间选组在共同修订后都答对该题 16/16。新增请求 0。 [选择回执与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_B5_DISAGREEMENT_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 独立开发

将先前知悉与不参考保密材料而开发分开。原 TRAIN 中 7 份无独立开发路径的合同与 1 份编号分项明确授权的合同均与原参考一致。固定 DEV 五臂各由 11/16 到 15/16，无退化，配对 95% 区间为 +6.25 至 +50.00 个百分点。归档 B5 同规则下候选驱动 16/16、按时间 15/16，分类和证据差的区间均包含零。累计 ContractNLI 四个内部臂 201/272、PARSE 192/272。新增模型请求 0。 [独立开发与五库累计指标](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_DEVELOPMENT_AND_FIXED_DEV_20261120.json)

## Revision 6 M2 威斯康星自住房候选

B7 提案新增正确的自住房分类引文，进入和候选均把共同所有的 142,200 美元住房按 75,000 美元估值。原文同信息核对只采纳分类。B8 前向第二份共同所有住房上没有候选分类新增，候选估值仍为 75,000 美元，原参考为 112,850 美元。限定候选与进入程序的 B8 分类和估值 F1 完全一致，固定 DEV 适用范围为 0/16。复用 32 笔原 TRAIN 响应，新增 0。 [威斯康星自住房前向结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_WI_HOMESTEAD_TRANSFER_20261120.json)

## Revision 6 MAUD 整节引用

识别完整节引用与两类可见义务的归属，并复核省略前的共同前导段。原 B5 一份 TRAIN 合同支持整节例外，归档两路均答对。固定 DEV 唯一命中共同前导段，五臂负面契约各从 12/16 到 13/16，普通经营各为 14/16。共用规则用于各臂，独立消融差为零。复用 2 笔 TRAIN 和 2 笔 DEV，新增 0。 [整节引用与五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_SECTION_REFERENCE_AND_FIXED_DEV_20261120.json)

## Revision 6 M1 MAUD 联合范围字段

把两个契约归属标志合成一个九值字段，保留两侧独立的已知及未决状态，100 个局部状态的消费者输出等价。沿用同一 10 份原 TRAIN，联合字段 16/20，旧合成 10/20，固定 15/20，直接 13/20。相对旧合成修正 6 项、退化 0 项，95% 配对区间为 +10 至 +50 个百分点。相对固定和直接的区间均跨零。模型每个实际读数只选择单侧归属，证据支持缓解旧读法的归属偏差。新增 10 笔、复用 30 笔。 [MAUD 联合范围配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_JOINT_SCOPE_20261120.json)

## Revision 6 M1 MAUD 疫情例外归属

把已验证的局部条款关系编译器接入两项完整原生契约判定。原 B1–B4 共 10 份带疫情线索的 TRAIN 母合同上，三路共用完整原节选、锚点和冻结读者。合成、固定和直接作答分别为 10/20、15/20、13/20。合成漏判 5 个普通经营正例，全部读到了疫情触发，其中 4 个读数把触发只连到了负面契约。30 笔均完成且正常解码，未达到前向扩验条件。 [MAUD 原 TRAIN 配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_COVENANT_FIT_20261120.json)

## Revision 6 M2 披露对象选组

用原 B5 已采纳提案和同一进入程序，在三份原文能同时核验员工与外部代理范围的 TRAIN 合同中选一组。候选驱动和按答案分歧均选中 B4 的双许可组并保留进入程序。按时间选中只有入站对象的合同并采纳提案。共享、逐例和同信息直接筛选一致。固定 DEV 三组均为 22/32，证据 F1 为 30.31%、30.31%、40.07%。候选驱动与按分歧逐项一致。原文成对规则在固定 DEV 无覆盖。复用 6 笔 TRAIN、32 笔 DEV，新增请求 0。 [披露对象选组结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RECIPIENT_ACQUISITION_20261120.json)

## Revision 6 M1 权利授予单任务比较

把原双任务消费者投影为权利授予单任务，在原消费者 729 个状态上核对输出等价。固定字段和合成接口分别使用 3 个和 2 个读数坐标。B6–B8 尚无前次配对读取的 8 份 TRAIN 合同上，合成、固定、同信息直接作答依次为 0/8、2/8、8/8，证据 F1 依次为 0%、20.83%、75.42%。8 份参考均为蕴含。合成读数给出 7 次未提及和 1 次未决。新增 24 笔冻结执行器响应均正常完成、无传输解码错误，共 137,372 tokens。该版本留在开发记录，未触发 DEV 扩验。 [权利授予配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_LICENSE_FORWARD_TRAIN_20261120.json)

## Revision 6 ContractNLI 协议披露

累计 B8 DEV 接入共用原文规则，识别直接禁止披露本协议及禁止公开参与本协议谈判的条款。四个内部臂在协议披露题各从 4/16 到 7/16，PARSE 从 10/16 到 11/16。全部 272 个假设分别为 197/272 和 188/272。同样使用新规则时，原 TRAIN 多数类回退为 13/16，B5 候选驱动为 9/16，按时间为 11/16。当前独立收益证据仍未达验收。新增模型请求 0，68 项检查通过。 [协议披露与五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_AGREEMENT_DISCLOSURE_AND_FIXED_DEV_20261120.json)

## Revision 6 ContractNLI 原始信息的明示标记

合并既有条款角色核对和免标记途径识别。区分原始信息的资格条件、副本标记、保留旧标识及留存确认。只有原定义或保密条款本身证明信息可按披露意图、性质或知情情形进入保密范围时，才给出相应反证。新增识别在四份原 TRAIN 找到可核查的免标记途径，四份都与原生参考一致。

累计固定 DEV 的五臂均由 4/16 到 12/16。每臂修复八题，退化零题，配对 95% 区间为 +25.00 至 +75.00 个百分点。ContractNLI 全部假设四个内部臂为 194/272，PARSE 为 187/272。各臂应用相同规则。65 项检查通过，新增模型请求 0。 [明示标记与五库累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CNI_QUALIFICATION_AND_FIXED_DEV_20261120.json)

## Revision 6 MAUD 知悉定义与五库累计 DEV

原 24 份 MAUD TRAIN 中，15 份由可见定义确认构成推定知悉。一份明确将「应合理知悉」的事实写入定义。将调查动作和应知条款绑定到同一知悉定义后，固定 DEV 新识别出合理调查和明示应知各一份。四个内部臂的知悉定义由 14/16 到 16/16，PARSE 由 15/16 到 16/16。调查和应知规则同样应用于各臂。

五库累计 B8 的联合臂现为 ContractNLI 186/272，Diversity 16/16，MAUD 知悉定义、负面契约、普通经营分别为 16/16、12/16、14/16，OpenExempt 分类和估值 F1 为 79.63%、68.48%，Airline 15/16。M1 在 Diversity 的两个启用臂各触发 16 次，同信息直接对照也为 16/16。累计矩阵中 M2 开关对应的同库程序一致，定向开发路径的训练选择另有独立回执。62 项检查通过，新增模型请求 0。 [知悉定义与五库五臂累计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_KNOWLEDGE_AND_FIXED_DEV_20261120.json)

## Revision 6 MAUD 跨节选恢复与负面契约

MAUD 的原请求已同时提供普通经营和负面契约节选。新增对齐器以省略号两侧保留的原文为锚，在另一节选中唯一定位被省略的片段，再核对例外是否管辖目标义务。B3、B4 的两份原 TRAIN 均恢复出疫情措辞，措辞落在负面契约的适用前导之外。

固定 DEV 两份合同恢复出相关措辞。一份的疫情例外直接修饰目标负面义务，五臂都修复同一题，负面契约由 11/16 到 12/16。另一份明示负面义务继承 A、C、D、E 项，疫情在 B 项。回放保持该案原预测，原生参考为 Yes。此处仅确定这项前导条款的继承范围。

原规则已接入累计 DEV 评估入口，同样给所有臂。当前改进属于共同输入处理。59 项检查通过，新增模型请求 0。 [原文配对与正式 DEV](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_MAUD_PARALLEL_EXCERPT_RELEASE_20261120.json)

## Revision 6 OpenExempt 分类的一般财产条款

从 56 笔 B2–B8 原分类响应定位适用性变化，再封存 B2、B6 的 16 笔配对。B2 仅保留两条有原文产权支持的俄勒冈一般财产索赔，分类 F1 由 38.99% 到 43.75%，同信息直接为 46.13%。B6 伊利诺伊兜底新增三条，F1 由 31.39% 到 38.53%，同信息直接同分。俄勒冈范围在后续三份原 TRAIN 适用，但没有同版本候选执行。伊利诺伊范围在 B7–B8 无符合条件的原 TRAIN。

用同一规则接到累计 B8 DEV 的五个臂。固定 16 份中各改写六份。四个内部臂的分类 F1 由 70.02% 到 79.63%，配对 95% 区间提升 2.64 至 18.23 个百分点。PARSE 由 68.63% 到 78.92%。M1、M2 各自的分类消融差仍为零。原生 EV 和其他库从原正式 DEV 继承。55 项检查通过，新增模型请求 0。 [TRAIN 配对和正式 DEV 修订](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_EC_GENERAL_PROPERTY_RELEASE_20261120.json)

## Revision 6 OpenExempt 资产绑定与家电金额迁移

复用 B2–B8 的 56 笔实际 EV 请求，27 份母来源两路均可评分。按原文资产清单把唯一的大小写、金额或里程后缀别名绑定到原名，保留每条索赔及其金额。候选表面新增的八条正确索赔中，四条只涉及资产名，包含 B2 车辆的两条法条、同批一条喷泉法条和 B6 住宅。资产绑定前后原生 F1 均为候选 15.48%、进入 16.41%。两路同样按原题司法辖区筛选后为 21.09% 和 23.99%。另复用固定 B8 DEV 的 32 笔，两个存档臂的资产键均无变化。

B8 候选对共同持有的智能恒温器新增 241 美元的正确索赔。以原题给定联邦法条、家电类别及明确产权限定迁移，在固定 DEV 只命中一份。进入与候选都对洗烘一体机报 1,275 美元，候选片段改写 0 份。相同原文的直接核对按单件上限改为 700 美元，EV F1 从 39.89% 到 40.41%。该三臂只共用资产绑定与辖区筛选。候选独立收益仍待验证。

54 项检查通过，新增请求 0，原冻结结果及曝光完整。 [候选索赔归因与家电配对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CANDIDATE_ASSET_BINDING_AND_APPLIANCES_20261120.json)

## Revision 6 处分后保留接口

M1 把处分前复制许可和处分后保留分开，将保留许可及禁留义务分别绑定到适用对象和作用域。合成把固定读者的五个字段压缩为两个关系及一个查全状态，243 个有限状态保留原消费者的分类和未决边界。12 份已源审原 TRAIN 上完成 36 笔实际请求。固定、合成、同信息直接三路均正确 4/12，且均修复 B7 的误判。合成独自识别三份保留许可，同时有六份分类未决。

从原文核对到五份合同存在明确的处分后保留例外。给三路同一原文证明后，合成、固定、直接分别正确 6/12、9/12、9/12，证据 F1 分别为 44.81%、52.87%、55.74%。将错误分类的证据记为零后，合成比直接低 13.70 个百分点，配对 95% 区间为 −27.41 到 −2.22。原训练选择器按初算联合证据分保存了合成候选，这次同信息证明比较否决了扩大验证。51 项检查通过，固定 DEV 派发 0 笔。 [实测与共享证明消融](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RETENTION_INTERFACE_AND_GRANTS_20261120.json)

## Revision 6 保留义务的局部否决

M2 根据 B1 源审的明确禁留条款，仅在候选把同类条款读成保留许可时，把保留义务交回进入读器。其余原生任务沿用 B5 提案。同信息直接臂得到相同的原文依据。复用固定 DEV 的 32 笔实测读数，16 份合同中触发两次，两份的进入读器和提案均输出允许保留，换读器只改变引文。整体分类和证据 F1 与原提案均相同，为 148/272 和 26.46%。同信息直接改判为 147/272。两处表面禁留分别受后文备份例外和限于指定交接文件的对象范围约束。

后续 B6–B8 三份原 TRAIN 另复核六笔请求。B7 一份合同分别规定销毁时不留副本、按请求处分复制件、关系终止时返还所有信息和副本。在该合同上，两路实测均误判为允许保留。既有源审把可能批准的再复制与处分后保留区分开。下一步可用该证据探索分开读取销毁、返还、复制和保留许可，并用其他已审 TRAIN 来源检验该关系。

47 项检查通过，本阶段新增模型请求 0，局部否决未纳入正式训练。 [局部否决与前向 TRAIN 证据](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RETENTION_SCOPE_20261120.json)

## Revision 6 保留义务的候选选组

M2 回放 ContractNLI 的 B5 PARSE 式原提案。两种策略共用 5 个源审组及 10 笔实际归档响应，每个所选组使用同样的两笔响应筛选。候选驱动按已观测的显式极性变化选中 B1 的保留义务错误，保留原读器。按时间选中 B5 的组，采纳提案。在同一组选定响应上，共享解释、逐例补全与字面直接检查的决定一致。

B4 与 B8 归档恰好包含这两种读器在相同 16 个 DEV 母样本上的实测响应，且原文、执行器配置和原生消费者等价。候选驱动与按时间选组的整体分类为 149/272 和 148/272，配对差 +0.37 个百分点，95% 区间 −3.68 至 +5.51。证据 F1 为 25.57% 和 26.46%。保留义务单项为 5/16 和 7/16。保留选组确实改变决定的证据，原 B5 历史结果不变。

44 项定向检查通过，新增执行器和教师请求均为 0，账本 14,835 笔、在途 0。独立原生收益仍待验收。 [选组记录与固定 DEV 配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_RETENTION_GROUP_TRANSFER_20261120.json)

## Revision 6 状态词实测与片段迁移覆盖

M1 将关系字段的真、假和未决改为对应的来源状态词。729 个状态的消费者输出全部等价。在原六份源审 TRAIN 上完成 12 笔配对请求，两路同样答对 7/12。状态词与同信息直接对照的证据 F1 分别为 72.22% 和 55.56%。差值来自同一份母样本的两项分类错误。按分类正确给证据计分，两路相同。此前接口在这批已源审 TRAIN 为 11/12，保留原版本和实际记录。

M2 核验已入库两项片段的迁移。B4 俄勒冈片段在 B5–B8 后续 16 份原 TRAIN 中均无符合产权、资产类别和法条的来源。B7 联邦限额片段在固定 DEV 的四份适用来源各有一个可核对位置，两路每处都给出相同的唯一金额。后续比较需来自能在其他实际母来源改变输出的已审范围。

43 项定向检查通过，新执行器请求 12 笔、教师 0。原冻结协议、结果和曝光保留。两项方法独立收益仍待验收。 [状态词配对与适用范围](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_STATUS_WORDS_AND_TRANSFER_CAPACITY_20261120.json)

## Revision 6 用途限制漏判与俄勒冈服装迁移

M1 复核已封存的用途与权利限制配对。合成读器的 10 个用途缺席输出都填了引文，同时把限定关系和不受限授权字段都填为否。有 2 个输出的原始引文包含完整用途限定。向各臂应用同一原文规则后，合成用途分类由 9/16 到 11/16，直接对照仍为 13/16。两任务合计 20/32 对 22/32，证据 F1 45.02% 对 32.84%，差值 +12.18 个百分点，95% 区间为 −6.12 至 +31.50。24 份原 TRAIN 的普通程序用途证据 F1 由 46.46% 到 62.01%，正确数保持 20/24。

M2 用 B4 同一母样本的原请求与两次金额改写选择俄勒冈服装估值片段。候选六个服装金额均正确，原程序四个正确、两个漏报，另有四处不适用的车辆豁免。B4 快照只允许在原文法条、服装类别及产权条件均明确时转移这两个法条。B5 前向 TRAIN 的四份来源均无适用条件，B4 的 16 份固定 DEV 有一份适用。复用 40 笔跨母来源归档请求后，片段实际改写 0 份，估值 F1 保持 16.12%，同信息直接校正为 16.95%。原 B4 整体候选的历史决定保留。

41 项定向检查通过，新增执行器与教师请求均为 0。两项方法独立收益仍待验收。 [完整配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_USE_SCOPE_AND_OREGON_TRANSFER_20261120.json)

## Revision 6 用途与权利限制配对及早期金额归档

M1 用相同的原文确定条款补齐三路的已归档 TRAIN 读数。六份源审合同的 12 项任务中，合成、固定字段和直接读器分别为 11、9、7 项正确，源审支持分别为 8、7、4 项。选定的合成接口已保存为 B8 快照。16 份原 DEV 上两路各完成 16 笔，用途和权利限制共 32 项。合成与同输入直接分别为 18/32 和 22/32，证据 F1 为 40.34% 和 32.84%。差值 +7.49 个百分点，95% 配对区间为 −12.81 至 +28.74。权利限制单项两路均为 9/16，合成修正与退化各 4 项，证据 F1 差 +11.69 个百分点，区间为 −18.46 至 +41.98。该快照保留供复现。员工披露的同条款证明在 6 份已源审母样本中核实 5 份正例，原 16 份固定 DEV 无命中。

M2 从 B2–B8 的 28 份原 TRAIN 核验原程序、实际提案的 56 笔估值请求，27 份两路均解码成功。按已验证的原题法条规则，联邦兜底豁免有 43 个金额位置，宾州一般豁免有 12 个位置。候选在两组均无正确正额。漏报的覆盖问题和出具错误金额分别记载。

37 项历史检查之外新增两项归档与来源限制检查，本阶段共 39 项通过。新增冻结执行器请求 32 笔、教师 0。两项方法的独立收益尚未达成。 [逐任务配对区间与金额归档](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_USE_LICENSE_AND_ARCHIVE_COVERAGE_20261120.json)

## Revision 6 证据分栏与分法条更新

M1 按许可条款是否引用定义名词来保留原文证据。在原 5 份固定 DEV 上，合成的证据 F1 从上一轮筛选的 48.10% 恢复至原解码的 52.10%，同输入直接对照仍为 72.00%。另在原 6 份源审 TRAIN 上实测两路角色分栏读器，共 12 笔。两路各有 5 笔重复编号被严格解码丢弃。在同一归档请求上去重后，合成与直接分别答对 5/6 和 6/6，证据 F1 为 41.67% 和 63.33%，源审支持数为 2/6 和 3/6。这一结构读器保留在 TRAIN，当前正式解码继续使用原版。

M2 按法条对成对金额断言筛选并保存 B7 技能快照。联邦条款选择提案金额，威斯康星条款保留原程序。B8 的 4 份前向 TRAIN 无适用输出。16 份固定 DEV 中有 4 份适用已选条款，候选金额的实测读数没有改变任何可迁移的原生位置。分法条路线估值 F1 为 45.03%，同源直接金额校正为 46.28%。B7、B8 和 DEV 保持相同原生分母。

37 项定向检查通过，新增执行器请求 12 笔、教师请求 0。原冻结结果及曝光记录通过哈希核验。两项独立收益仍待验收，Goal 保持活跃。 [逐臂结果及触发](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_ROLE_QUERY_AND_SCOPED_AMOUNTS_20261120.json)

## Revision 6 引文角色与实测金额

M1 对原始配对读数实施同一引文筛选。6 份 TRAIN 的独立源审支持删除 3 条多余引文，已引用的必需证据全部保留。5 份适用 DEV 的合成与同输入直接读器仍均为 5/5。合成证据 F1 从 52.10% 到 48.10%，直接读器均为 72.00%。保留实测结果，正式选择继续使用原解码。

M2 从 B7/B8 归档核对 32 笔原生请求。B7 一份 TRAIN 的 4 项可核对正额中，两路各错一处。原程序在联邦每件 $700 的上限给出 $800，提案在威斯康星同件应为 $800 的位置给出 $105。B8 在此窄范围内无适用来源。同信息共享与直接检查同判。把同样的金额校正应用于两个固定 DEV 臂，两路各修正 1 份、退化 0 份，估值 F1 分别从 45.03% 到 46.28%、从 46.13% 到 47.38%。两路差仍为 +1.10 个百分点，配对区间为 −4.56 至 +8.92。

新增模型请求 0，34 项定向检查通过，连续账本 14,779 笔、在途 0。两项独立收益仍待验收。 [原生指标、触发与配对区间](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_CITATIONS_AND_STATUTORY_AMOUNTS_20261119.json)

## Revision 6 跨条款读数与 M2 明示断言

M1 在原八批上复用六份 TRAIN 合同的 12 笔跨条款读数，保存并复用接口库。固定与合成分别答对 0/6 和 6/6，合成的 3 份许可同时通过独立源审。5/16 份固定 DEV 合同适用于该接口，TRAIN 选型在五份均调用合成。合成和同输入单题直接对照均为 5/5，原共用程序为 4/5，固定字段对照为 0/5。合成、直接对照的证据 F1 分别为 52.10% 和 72.00%。合成额外正确的一份可由原文许可证实。同输入直接对照也正确，独立原生收益仍待建立。 跨条款拟合入口 `convergence_revision6_contract_links.py` · 同输入直接对照 `convergence_revision6_contract_link_control.py`

M2 已把明示金额和漏报分开。B7 候选驱动组选中的编辑只使进入程序丢失一个已答引文。按明示断言计，两路共有的四个位置中，进入程序三项可配对、一项未观测，候选四项可配对，双方均无显式金额矛盾。校正后两种选组都保留进入程序，共享与直接检查一致。B4 的存档编辑也已用同一语义复算。按 B7 已审法域限制部署的 3 份 DEV，其估值 F1 为 57.59%→54.26%，属于归档诊断。 正式 M2 校正 `convergence_revision6_candidate_assertions.py`

29 项定向检查通过，新增冻结执行器 15 笔，教师 0。连续账本 14,779 笔、在途 0。原 TEST 终态、冻结源码 72 份、协议和曝光记录通过校验。当前 Goal 保持活跃。 [跨条款与明示断言结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_LINKS_AND_ASSERTIONS_20261119.json)

## Revision 6 正式路径

ContractNLI 通过正式拟合入口按原批次校准，持久化每批关系接口库，再用于固定 DEV 的跨母来源选择。复用 4 份已源审 TRAIN 合同的 8 笔精确请求，新增 14 笔 DEV 配对读数。7/16 份合同落在员工披露作用域内，原共用程序、固定字段、TRAIN 选型和强制合成分别答对 7、6、6、3 份。TRAIN 选型在 7 份适用 DEV 上保留固定字段。合成读器在 4 份输出 `unread`，其中 3 份固定读器正确；这些读数均正常结束。 正式合同入口 `convergence_revision6_contract_fit.py`

OpenExempt 的候选驱动拟合以 B7 实际提案和现行程序为输入。4 个可用所有权组下，两种选组同选一组。候选读数均为未知，共享与直接筛选均保留现行程序。金额编辑的等预算比较中，两种选组从同一 3 组候选中选到不同组，各复用 2 笔原请求。在最初把漏报按零值比较的覆盖口径下，候选驱动组采纳了提案。上节的明示断言校正已更新该决定。B8 前向 TRAIN 上，估值 F1 由 43.75% 到 47.50%，分类由 59.79% 到 45.63%。固定 DEV 只切换估值技能，16/16 份来源均正常生成。同一公共控制下 F1 由 45.03% 到 46.13%，2 份改善、3 份退化，母来源配对 95% 区间为 −4.56 至 +8.92 个百分点。共享筛选和直接筛选同判。 正式选组入口 `convergence_revision6_candidate_fit.py` · 等预算金额选组 `convergence_revision6_candidate_edits.py` · 估值 DEV `convergence_revision6_candidate_dev.py`

两条正式路径本轮已结算。Diversity 复用已交付的 16/16 同信息强对照，MAUD 与 Airline 本次未启用新路径，复用已封存的 DEV 结果。共新增 48 笔冻结执行器调用，教师调用 0。连续账本 14,764 笔，在途 0。原 TEST 终态、曝光与 72 份源码通过校验。原 Goal 保持活跃。 [五库分母、激活、逐臂指标与升降](../reports/legal_skill_convergence_20261117/paper/tables/REVISION6_FORMAL_PATHS_20261119.json)

## Revision 5 历史交接

用户已恢复同一研究 Goal（`01a1edc7-ae76-7441-acaf-be2240b0b4b1`）。当前工作安排采用 revision 5，已从指定提交 `56ed2142df80c47ce155351902916b10ae626904` 校验并同步三份入口。工具中的原 Goal 文本继续保留原研究对象和验收条件。原 `protocol.json` 由冻结轮次使用。

- [新版 PLAN](../reports/legal_skill_convergence_20261117/PLAN.md) · [接续协议](../reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json) · [服务器指令](../reports/legal_skill_convergence_20261117/SERVER_GOAL.md)
- 已结算 128 来源八批训练、五库冻结 TEST、消融、强对照及论文初稿。冻结 TEST 终态 `dbbc3b355cad2328b14f7255bfe4a23b9a8b449c80d581159f0c99c3bc93fd7d`。恢复时连续账本为 14447 行，在途 0；最新结算见下。
- 本阶段只补充了决定下一步所缺的证据。M1 对齐候选和读数、训练选择并追到库与原生结果。M2 对齐原始教师请求、反馈、候选、共享筛选和最终库，保留同信息强对照。发现可实施的新缺口后使用独立开发版本做最小 TRAIN/DEV 比较。
- 原候选库存的独立验证容量结论适用于后续独立确认。这一阶段继续在现有 TRAIN/DEV 上工作，保留原 TEST 的曝光事实。
- 恢复时读取 `handoff/run_state.json`、实际任务、账本及源码绑定。入口同步回执 `handoff/continuation_revision5_authority_20261119.json`，以下记录按当时日期保留。

## Revision 5 当时的阻断状态

当时原 Goal 已登记为 `blocked`。连续三次核对均未找到有原文与 TRAIN 读数支持、可与同信息强对照产生可归因原生差异的新候选。五库累计正式 DEV 的四组机制消融输出逐库一致，两项贡献的独立原生效果仍未达到验收条件。现有训练、冻结 TEST、消融、论文与归档证据已结算。账本为 14,716 笔，在途 0。恢复以新的源文和 TRAIN 证据或用户修改验证范围为依据。 [阻断说明与证据](../reports/legal_skill_convergence_20261117/GOAL_BLOCK_20261119.md)

## Revision 5 五库累计正式 B8 DEV 已封存

正式入口把已核验的 ContractNLI 来源绑定与 OpenExempt 资产键、宾州一般金额规则接入同一份五库 B8 DEV。五臂各含 80 个母来源、384 个原生视图。Diversity、MAUD 和 Airline 逐项复用上一次正式预测。1,920 个原生视图全部通过封印校验。 [执行代码](../experiments/convergence_revision5_release_dev.py) · [逐臂指标、区间及机制计数](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CUMULATIVE_FORMAL_DEV_20261119.json)

原 B8 DEV 与本次累计修订相比，联合臂的 ContractNLI 分类为 156/272→186/272，证据 F1 为 36.37%→48.92%。Diversity 为 14/16→16/16。MAUD 知悉定义、负面契约、普通经营依次为 8/16→14/16、9/16→11/16、14/16→14/16。OpenExempt 分类、估值 F1 为 50.19%→70.02%、44.37%→68.48%，16 项估值的 MARE 为 2.588→0.040。Airline 为 2/16→15/16。

M1 在两个启用臂各调用 16 次 Diversity 关系接口，其他四库的正式调用为 0。两组 M2 消融的 B8 程序在五库分别完全一致。四组方法消融的原生输出逐库一致。联合臂相对 PARSE 的差异保留在完整表中，包含 MAUD 知悉定义低一题。

13 项定向检查通过。新增模型请求 0，连续账本 14,716 笔、在途 0。冻结协议、72 份源码、TEST 终态及曝光回执通过校验。正式开发结算见 `handoff/revision5_release_B8_DEV_terminal_20261119.json`。

后续派发核对已将 MAUD 两版局部接口的 8 笔原始响应对齐到现行 TRAIN 契约节选。两处被读例外均无疫情触发。原 TRAIN 中 8 份有疫情线索但共用规则未决定作用域的合同，两路原程序共同答对 7 份，另 1 份为已记录的嵌套例外口径分歧。M2 沿用既有 35 组真实投影的累积证据，二元和联合筛选没有不同决定。本轮没有新候选达到派发依据。已核验的回执见 `handoff/revision5_followup_applicability_receipt_20261119.json`。

## Revision 5 ContractNLI 披露协议本身的来源绑定接入正式 B8 DEV

把披露行为绑定到协议存在或谈判事实。明示规则区分主动禁止、被动禁止和不负披露义务，并按原文编号补齐同一禁止的紧邻续句。只涉及考虑交易的披露条款保留为解释范围诊断。原 24 份 TRAIN 上普通教师 10/24→11/24，PARSE 13/24→14/24。固定 B8 DEV 的四个内部臂该项由 3/16 到 4/16，PARSE 由 9/16 到 10/16。接入后 ContractNLI 总分类为 186/272 与 179/272。五臂均改善一项分类、无分类或证据退化；正式结果使用重复查看过的开发集。 [代码](../experiments/convergence_revision5_cni_agreement_event_attachment.py) · [完整结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_AGREEMENT_EVENT_ATTACHMENT_20261119.json)

复用 30 笔固定、合成、直接读数。在探索性宽口径覆盖下分别为 4/10、7/10、3/10；合成减固定的配对 95% 区间为 −10 至 +70 个百分点。留一母来源的 TRAIN 多数类为 8/10。固定 DEV 上的明示规则加 TRAIN 多数类诊断为 11/16，仍有未提供来源证据的多数类预测。正式流程采用明示规则，保留原有未决输出。M1/M2 的四组 ContractNLI 消融仍一致。

15 项检查通过，新增模型调用 0，连续账本 14,716 笔、在途 0。冻结协议、72 份源码、TEST 终态和曝光记录通过校验。回执见 `handoff/revision5_CNI_agreement_event_attachment_terminal_20261119.json`。Goal 保持活跃，下一项实验需有超出已核验对照的可归因 TRAIN 缺口。

## Revision 5 ContractNLI 递交对象接入正式 B8 DEV

按条款识别处分证明、获准带出物品的归还、文书签署、通知递交和小节标题。新增的两项 TRAIN 请求限定判断均与已存源审一致。加入正式 B8 DEV 后，五臂的终止处分分类由上一正式组合的 5/16 提高到 14/16。四个内部臂的 ContractNLI 分类由 176/272 到 185/272，证据 F1 由 45.67% 到 48.80%，共 9 项分类改善、0 项分类退化、1 项证据退化。PARSE 由 169/272 到 178/272，证据 F1 由 37.17% 到 40.29%，有同样的逐题变化计数。其余四库复用 B8 正式结果。 [代码](../experiments/convergence_revision5_cni_disposition_roles.py) · [正式集成和筛选回放](../experiments/convergence_revision5_cni_disposition_roles_gate.py) · [逐臂评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DISPOSITION_ROLES_20261119.json)

源角色规则相对上一局部事件修订提高 2/16，配对 95% 区间为 0 至 +31.25 个百分点。额外识别「书面请求返还或销毁、接收方应遵从」后到 15/16，该句式仅有探索性 DEV 证据，正式流程采用 14/16 版本。四项 M1/M2 比较在 ContractNLI 的原生输出仍完全一致。核对 B8 三份 TRAIN 合同的 12 笔正式响应，在现行程序与候选同时加入同一规则后，普通教师与 PARSE 候选收益分别为 −5.88、−15.69 个百分点，仍保留现行程序。

11 项检查通过。账本 14,716 笔、在途 0，冻结协议、72 份源码、TEST 终态和曝光记录均通过校验。回执见 `handoff/revision5_CNI_disposition_roles_terminal_20261119.json`。Goal 保持活跃。后续方法验证需要一项能与同信息直接读数分开的 TRAIN 证据。

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

统一对照后，协议是否禁止披露自身存在一项仍是 ContractNLI 最大残差。实现按同一原文条款组绑定披露行为、效力和对象的接口，在公共规则无法确定、且同句含候选披露行为和事件线索的全部 10 份 TRAIN 合同上比较。固定、合成和直接作答共用全文与原文编号，直接作答可引用组外条款。30 笔 Qwen 均结算，原生正确数分别为 3/10、1/10、1/10。合成有九份报告范围未定。用原文编号纠正两种结构化接口互相矛盾的组外标记后，原生正确数变为 3/10、5/10、1/10；合成相对固定的配对区间仍包含零。逐来源排除自身标注的 TRAIN 多数类参照为 8/10，说明修复后的合成接口仍漏掉关键少数类证据。原生正确与引文 F1 的联合得分同时保留。

TRAIN 上，独立的公共对象规则把普通教师从 9/24 提到 11/24，固定 B8 DEV 保持 3/16，PARSE 从 9/16 到 10/16。条款绑定覆盖 13 个固定 DEV 公共文本，现有 TRAIN 结果不足以推进该接口。新增 30 笔 Qwen、154,532 tokens，教师 0，账本 14,716 笔、在途 0。保留上一版五库统一对照及正式评估门槛。 [实测及回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_KEYED_DISCLOSURE_20261119.json)

## Revision 5 五库统一开发对照已结算

用户将研究推进用的 Codex 切到 6.2-sol high，原实验仍按 Qwen3-8B thinking-off 与冻结教师绑定执行。实装统一的原生后处理入口，让五个既有臂按相同的公开规则处理原 B8 DEV 的 80 个母来源、每臂 384 个视图。预测先单独封存，随后按原评分器逐项复算。普通教师臂的 ContractNLI 分类为 156/272→176/272，Diversity 为 9/16→16/16，MAUD 知悉定义为 8/16→14/16，OpenExempt EV F1 为 44.37%→65.36%，Airline 为 2/16→15/16。各库分项、升降计数及母来源区间一并保存。

两组 M1 消融各原有 7 个原生输出不同，共用规则后各 384 个输出逐项一致。两组 M2 消融在两版本的开发回放上均逐项一致。两项方法同时进入修订正式流程的证据门槛仍未满足。已经运行的统一入口可在后续对照中复用，原冻结版本保留。新增模型请求 0，账本 14,686 笔、在途 0。 [五库回放及分臂结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_COMMON_NATIVE_DEV_20261119.json)

## Revision 5 ContractNLI 原文条件下的接口缩减已结算

把唯一可核实的用途限制或否定授予条款作为公共前提，重编译固定与合成接口。对完整消费者回执逐状态验证。仅确定一个判断时，固定与合成分别需读 4 和 3 个字段。两项均已确定时，两路仍各须读两个原回执要求保留的相反授权状态。只比较原生标签的诊断可省去这两个字段。按完整回执计算，原 24 份 TRAIN 的固定和合成字段总数为 130 和 89，固定 B8 DEV 的 16 份为 92 和 62。这是编译计数，复用原响应回放。

原文前提覆盖 TRAIN 7 项、固定 DEV 2 项，普通教师与 PARSE 均已答对覆盖项及这些合同中的其余判断。上轮 18 笔配对施加同一原文前提后，覆盖合同余下两项由固定答对 1 项，合成和直接作答各答对 2 项。两路共用来源事实，合成在本次有覆盖的范围内未取得超出直接作答的原生收益。新增模型请求 0，连续账本 14,686 笔、在途 0。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_CONDITIONED_USE_LICENSE_20261119.json)

## Revision 5 ContractNLI 从属条款引文回放已结算

按原文条款编号向前核对连续分项，只在已有引文命中从属条款且能唯一绑定前导句时补引。原 24 份 TRAIN 中有五份用途限制和两份权利授予符合条件。固定 B8 DEV 的 16 份中有两份用途限制符合条件。保留既有引文并补前导句后，DEV 普通教师的用途限制证据 F1 从 24.61% 到 28.15%，PARSE 从 23.75% 到 25.63%。只保留已核实的完整条款组合进一步达到 29.40% 和 26.88%，作为引文裁剪敏感性检查。原生标签均保持原判，两任务合计的母来源配对区间下端均为零。

对上轮 18 笔配对响应共用引文规则后，前段固定与合成的完整源文支持分别为 4/6 和 3/6，原选择仍为固定。两接口在跨片段否定授予上均漏掉实际条款，引文补齐无法恢复该项，直接作答已有完整引用。新增模型请求 0，账本 14,686 笔、在途 0。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_CLAUSE_WITNESS_20261119.json)

## Revision 5 ContractNLI 用途限制与权利授予配对已结算

六份原 TRAIN 合同各运行固定字段、合成关系与同输入直接作答。六个局部前提在 729 个有限状态上验证，合成接口缩为四个字段并保持原消费者。前段六项判断中固定和合成都答对 5 项，完整源文支持为 3 项和 2 项，预设选择器选中固定。

后段六项判断中，固定、合成和直接作答分别答对 3、4、4 项，证据 F1 为 32.78%、52.78%、38.33%。合成正确识别同份合同中两项未提及，但和固定一样漏掉另一份合同跨片段的否定授予条款，直接作答引用完整。源审在后段答对 6/6；前段有一处明示用途限制与原标注不同。原 24 TRAIN 中分别有一份拆分否定和一份紧邻先行词，固定 B8 DEV 16 份均未出现这两种形式。当前结果保留固定路线，尚无独立收益支持启动后续验证。

18 笔 Qwen 共 76,942 tokens，教师 0。首笔已结算后，驱动因缓存标记与账本对象不相等而停止。沿用原绑定及原调用编号恢复，首笔未重发。23 项检查通过。连续账本 14,686 笔、在途 0。 [配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_USE_AND_LICENSE_20261119.json)

## Revision 5 OpenExempt 共享反馈的分类收益已定位

复用首轮两笔教师原请求的核验，追到 20 笔原生 EC 响应。共享反馈讨论的是鹦鹉的归属。首轮共享提案唯一新增的正确引文来自同案胸针，原文把胸针列为申报人的已知资产。旧产权模板把这句与单纯持有都归入未决。用同一原生输入中明确的资产归属、个人用途前提及所附伊利诺伊州条文直接核对，进入程序的 EC F1 从 27.50% 到 35.83%，四份输出逐项复现首轮共享提案。金额和鹦鹉归属保留原读数，历史共享筛选决定保留。

在原 32 份 TRAIN 上，共用规则覆盖两份来源。普通教师与 PARSE 的 EC F1 分别从 35.78% 到 37.34%、45.89% 到 47.63%，两个配对区间下端均为零。固定 B8 DEV 的 16 份均无覆盖。该结果补齐首轮分类收益的来源归因，尚无足以启动独立验证的机制收益。19 项检查通过，新增请求 0，连续账本 14,668 笔、在途 0。 [评分与来源绑定](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ILLINOIS_ASSET_ATTRIBUTION_20261119.json)

## Revision 5 ContractNLI 同句引文修复已结算

复核六份 TRAIN 的 12 笔固定与合成读数，以及六笔归档直接作答。一条完整响应在同一句中读取了披露许可及当场定义的接收人，旧解码器因同一证据编号重复丢弃整条响应。两臂共用引文归并，保留原文编号和真正独立的定义引文。只恢复这一题。合成精确匹配 5/6→6/6、证据 F1 37.62%→54.29%，固定为 0/6 和 16.67%。归档直接作答为 6/6 和 58.33%，也已准确引用该句。

定义成员关系与签名作用域两组的另 26 笔原始响应均无重复引文。此项修复可解释一条读数丢失，现有证据没有给出超过直接作答的净收益或独立 DEV 验证依据。新增模型请求 0，连续账本 14,668 笔、在途 0。接续仍需有真实原生差异、可用同信息对照核验的候选。 [配对读数与评分](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COLOCATED_CITATION_20261119.json)

## Revision 5 MAUD 已采纳候选的共用作用域回放已结算

逐笔核对 B6 普通教师、B6 PARSE 和 B8 PARSE 的 18 笔归档响应及已保存程序。三项已采纳提案原先分别多答对 1、1、2 题。给进入程序和候选共用知悉定义与契约作用域核对后，两路逐题同判，三组分别各为 9/9、9/9、8/9。普通经营契约检查复用了已核验的母合同定义，属于回顾性对照。

B8 知悉题的完整定义以已知事实为准，并纳入已收到的书面通知。将这一来源条件送入原有限消费者后，无需再读字段即可判定该题。原 24 份 TRAIN 余下四份均有截断或省略，剩余固定与合成字段数为 8 和 4。固定 B8 DEV 没有同形式的通知定义，两路知悉题保持 14/16 和 15/16。

新增模型请求 0，连续账本 14,668 笔、在途 0，20 项检查通过。字段缩减的剩余覆盖均来自上下文不完整的节选。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_ADOPTION_SCOPE_20261119.json)

## Revision 5 ContractNLI 逆向工程的动作与证据范围已结算

按接收方、逆向工程动作及对象核对条款。同一规则用于普通教师和 PARSE，两路在原 TRAIN 上均从 3/24 提高到 23/24。余下一份原生正例的参考引文仅约束出版、复制和使用，保留标注与源文判定的差异。原生总收益为正的五项提案共 63 个配对，逆向工程标签唯一变化来自截断。在保留已完整返回的题目后，候选与进入程序在该题逐项同判。

固定 B8 DEV 两路均从 1/16 到 16/16，单句对照已经复现全部标签。根据同一 DEV 中的义务列表反馈，将连续分项连回约束接收方的前导条款，证据 F1 从 97.92% 到 100%。这一步复用了已查阅的 DEV。

新增模型请求 0，连续账本 14,668 笔、在途 0，31 项检查通过。该原生收益由共用源文检查解释。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_REVERSE_ENGINEERING_20261119.json)

## Revision 5 OpenExempt 俄勒冈资产资格与用途编辑已结算

按两任务实际原文和随题俄勒冈条款，排除长笛的机动车估值，并在产权已确立的分类原文补入乐器引文。B7 提案的两处冲突减为一处。两路在四份 B7 TRAIN 上的分类 F1 各增 1.59 个百分点，原生估值 F1 均保持。受影响的提案估值在次要全输出计数下少一条误报。既定 B8 DEV 的 16 份来源中此规则覆盖为零。

余下一处涉及画作能否归入家庭用品。用途编辑将同一幅画明确限定为营业转售，保留原产权、价格及条款。独立补全允许四个签名，共享解释允许两个。相同信息的直接规则在全部 81 种已知和未知组合上与共享枚举同判。用途编辑只做离线核验，保留原 TRAIN 标注及选择。

新增请求 0，连续账本 14,668 笔、在途 0，27 项检查通过。该用途编辑未形成可区别于强对照的新监督依据。 [证据与回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_OREGON_ELIGIBILITY_20261119.json)

## Revision 5 OpenExempt 分类断言与 B7→B8 选择回放已结算

核对 B7 和 B8 各四份原 TRAIN 的 32 笔执行响应。按原数据生成器的姓氏复数规则，在 B8 恢复一处联名债务人称呼绑定。两路采用同一辖区、金额、兜底和资产类别检查。通配条款补出的资产行只支持该项引文，其余未作答类别保持未决。若把新行视作已答全类别，B7 两路各有 22、15 处冲突。按实际断言核对后为 0、2，原候选的两处冲突均保留。

B7 提案在共用检查后高 8.44 个百分点。独立补全采纳提案，共享筛选和同信息直接核对均保留进入程序。B8 归档前向回放中，保留程序的原生双任务均值高 4.25 个百分点，配对 95% 区间为 [−4.86, 14.82]。共享与直接核对逐项一致。

新增请求 0，账本 14,668 笔、在途 0。27 项检查通过。相对同信息强对照的独立收益仍未建立。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ASSERTION_COVERAGE_20261119.json)

## Revision 5 ContractNLI B5 共用作用域与回归门槛已结算

给进入程序和 B5 提案应用相同的完整记录恢复、协议存在性覆盖检查及既有招揽规则。旧批次差距从少 24 题缩至少 7 题，修正后为 110/204 对 103/204。当批提案为 40/51，进入程序为 37/51。即使将截断项 17 题全计对，旧批次的提案上界仍为 109/204，原保留决定成立。

固定 B8 DEV 中，初版协议存在性检查覆盖三份合同，其中一份明示协议本身须保密却被判为未提及。补上保护条件后在同一 DEV 回放，普通教师该题由 3/16 到 4/16，PARSE 由 9/16 到 11/16。配对 95% 区间分别为 [0.00, 18.75] 和 [0.00, 31.25] 个百分点。

本轮共用检查的收益仍不足以建立两项贡献的独立效果。新增请求 0，账本 14,668 笔、在途 0，27 项检查通过。 [回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_RETENTION_CONTROLS_20261119.json)

## Revision 5 ContractNLI 截断响应与候选选择已结算

复用 93 笔原 TRAIN 和 64 笔 DEV 响应，对普通教师及 PARSE 同样保留通过原生格式和索引校验的完整题目。B5 普通教师提案的截断响应恢复 13 题，其中 10 题正确。旧批次正确数由 82/204 到 92/204，进入程序为 106/204。即使这笔响应的 17 题全部正确，提案上界仍为 99/204。五项提案的采纳决定逐项一致。

B1 DEV 普通教师由 134/272 到 143/272，证据 F1 由 28.90% 到 29.04%。PARSE 和 B8 DEV 两路均保持原读数。该回放给出了可量化的共用解析修复，独立贡献证据仍不足。新增请求 0，账本 14,668 笔、在途 0，17 项检查通过。 [归档回放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_PARTIAL_WIRE_20261119.json)

## Revision 5 ContractNLI 存续作用域与提案追踪已结算

按同一协议、终止事件和义务核对原生存续问题。24 份 TRAIN 中，10 份匹配该原文证据及原生参考，另有一份原文与参考分歧。该合同的一年总体期限明确保留十八个月条款。将十八个月在原文中分别改为十二和六个月，三份文本的局部跨期结果依次为真、假、假。共享、逐例和单解释都产生同一签名。

固定 B8 DEV 有三份明确条款。普通教师和 PARSE 的正确数保持 12/16 和 11/16，PARSE 的官方证据 F1 从 23.33% 到 35.83%，配对 95% 区间为 [0.00, 31.25] 个百分点，单条款对照逐份复现。B3–B5 五个原生总收益为正的提案共 63 个配对，存续标签修正五次、退化六次，11 次变化均位于严格原文证据覆盖之外。新增请求 0，账本 14,668 笔、在途 0，15 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_SURVIVAL_SCOPE_20261119.json)

## Revision 5 ContractNLI 信息类别与定义绑定已结算

自动规则把原生引文中的类别或传达形式连回同一份合同的定义。六份配对合同中，从合成接口已引的成员补齐上下文，四项非技术类别均恢复。两项原生问题合计为固定 9/12、合成 12/12、直接作答 11/12。让同信息对照遍历全文后，合成和直接作答均为 12/12。

全文核对先覆盖 17 份 TRAIN 类别正例中的 12 份。按 TRAIN 定义措辞扩展后覆盖 16 份，PARSE 的类别正确数由原 11/24 到第一轮 18/24、扩展后 20/24，普通教师保持 17/24。固定 B8 DEV 的两轮预测逐项相同，PARSE 由 5/16 到 8/16，配对 95% 区间 [0.00, 37.50] 个百分点，证据 F1 由 34.72% 到 45.97%。普通教师保持 12/16。该收益可由全文直接核对实现。新增请求 0，账本 14,668 笔、在途 0，18 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DEFINITION_BINDING_20261119.json)

## Revision 5 ContractNLI 定义成员与传达形式比较已结算

六份原 TRAIN 合同共 18 笔真实读数。固定字段、合成关系和直接作答共用全文、原生索引、冻结读者及预算。两项原生问题的正确数分别为 6/12、8/12、2/12，归档普通教师为 10/12、PARSE 为 9/12。合成相对固定的配对增益为 16.67 个百分点，95% 区间为 [0.00, 33.33]。合成和固定都正确识别六份合同的口头形式，也都漏判四份原文已纳入的非技术类别。

归档引用表明，四个类别正例中，合成已经给出三份足够的引用组合，固定及直接作答各一份。直接作答六次判断口头形式未提及，但六次均已引用足以支持的条款。用同一份回顾性源审核查既有引用，合成、固定及直接作答的类别正确数分别为 5/6、1/6、3/6。该诊断用于定位引用之后的错误。新增 18 笔 Qwen、101,786 tokens，教师 0，账本 14,668 笔、在途 0，12 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DEFINITION_MEMBERSHIP_20261119.json)

## Revision 5 OpenExempt 资产类别作用域已结算

用两条公开法条的适用类别及每个视图的产权证据，修正 B7 兜底估值后剩余的四项冲突。补回两项有产权和类别依据的分类，去掉两项类别明确不适用的估值。B6 仍选择只替换分类。回顾性 B7 分类 F1 从同条件进入程序的 60.96% 到 62.02%，估值均为 45.98%。

在原 32 份 TRAIN 和固定 B8 DEV 的 16 份来源上回放同一规则。DEV 普通教师和 PARSE 的分类 F1 分别为 51.52%→53.29%、50.37%→52.15%，估值 F1 为 64.32%→65.36%、60.26%→61.30%。四项配对区间下端均为零。两臂共 54 个已答资产向量上，共享筛选与同信息直接核对同判，未出现额外拒绝。新增请求 0，账本 14,650 笔、在途 0，19 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_CATEGORY_SCOPE_20261119.json)

## Revision 5 OpenExempt 联邦兜底估值与 B7 路由已结算

按原生 EV 指令为每个资产和法条组合单独计算 `§ 522(d)(5)` 基本额度及未动用的住宅额度，按给定辖区和源文产权条件确定适用。逐项计算与同信息直接公式一致。TRAIN 的 49 项和固定 B8 DEV 的 29 项估值全部匹配原生参考。TRAIN 普通教师和 PARSE 的 EV F1 在既有资产金额上限基础上从 20.38% 到 31.67%、从 17.88% 到 29.83%。DEV 分别从 49.50% 到 64.32%、从 44.31% 到 60.26%。

两路共用兜底规则后，B6 仍选只替换分类。B7 新增资格冲突由 10 项降到 4 项，固定路线的分类 F1 是进入程序的 57.71% 对候选的 57.02%。逐来源回放保留一份进入程序并应用其余三份候选分类，两任务均值增 1.56 个百分点，配对 95% 区间为 [−0.31, 5.00]。筛选使用两路归档预测，直接核对可复现。新增请求 0，账本 14,650 笔、在途 0，17 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_WILDCARD_REPLAY_20261119.json)

## Revision 5 MAUD 知悉定义的节选约束与读数缩减已结算

对原 24 份 TRAIN 和固定 B8 DEV 的 16 份合同核验 68 笔归档响应及其实际请求。用定义中的明示事实约束原 48 状态消费者，节选足以决定 TRAIN 19 份、DEV 11 份。保留未决处的原预测后，普通教师与 PARSE 的原生正确数在 TRAIN 分别为 9/24→24/24、10/24→23/24，在 DEV 分别为 8/16→14/16、10/16→15/16。编译证明给出的待读字段总数在 TRAIN 为固定 9、合成 5，在 DEV 为固定 11、合成 6。两种接口均保持有限域内的消费者输出。同信息直接规则逐份复现已由节选确定的判断。

24 份 TRAIN 节选均可对齐原母合同，其中一份截在公司一侧的实际知悉，母合同续文对双方均要求合理调查。原生评分保持节选范围，完整定义单独记为解释敏感性。固定 DEV 两种剩余误判措辞均缺对应 TRAIN 例，保留为反馈。新增请求 0，账本 14,650 笔、在途 0，13 项相关检查通过。更广核查中的旧源审持久化检查缺历史登记项 `artifact_root`。原冻结协议、72 份源码、原结果表和曝光回执已校验。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_KNOWLEDGE_RESIDUAL_20261119.json)

## Revision 5 OpenExempt B6 分任务选择与 B7 前向回放已结算

核验 32 笔原生归档响应。用原 B6 训练收益选择只替换分类、保留进入程序的估值。加入公共辖区和金额对照后，B6 仍选择同一路由。该路线在原 B7 读数上的分类 F1 为 24.51%→25.17%，但两路同样排除辖区外引文后为 53.89%→39.43%。B7 形成 10 项新增资格冲突，集中在两份来源。B6 未见这些新增冲突。

用 B7 归档读数做逐来源回放：新增冲突的两份保留旧输出，其余两份采用候选分类。分类 F1 为 55.40%，估值保留 29.19%，两任务均值相对同信息进入程序增加 0.76 个百分点，配对 95% 区间为 [−2.73, 5.00]。直接核对用同一源文事实作出相同决定。逐来源比较需要两份分类读数，保留为回顾性对照。新增请求 0，账本 14,650 笔、在途 0，23 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_B6_TASK_ROUTE_20261119.json)

## Revision 5 OpenExempt 共同断言位置核查已结算

核验五组进入程序与提案的 32 笔归档 TRAIN 投影响应。每组在两路共同作答的位置上逐项相同。B8 有类型读数中，候选保留一组共享解释，进入程序没有。仅移除进入程序在候选弃答位置的两个零额断言即可复现差异。首轮共享反馈提案相对已采纳程序多答一个零额，足以与原先两项兼容断言构成冲突。保留原共享拒绝决定，逐例独立补全仍相容。

给定同一组公开估值和请求分量，直接按同一个所有权状态核对，在每组全部 81 个部分读数状态上与签名枚举一致。此轮未识别到共同作答位置上的机制差异。新增请求 0，账本 14,650 笔、在途 0，22 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_MATCHED_PROJECTION_SUPPORT_20261119.json)

## Revision 5 ContractNLI 法定披露通知的引用与覆盖核查已结算

在原 24 份 TRAIN 上，同句核对使普通教师和 PARSE 都由 17/24 到 24/24。将明确的交叉引用和相邻触发条款连到通知义务后，两路各有三份补充证据，证据 F1 各提高 6.81 个百分点。原 B3–B5 五项整体原生为正的提案共 63 个来源－提案配对，应用同一源文检查后，进入程序与提案的标签和证据逐项相同。

初版规则在固定 B8 DEV 两路由 12/16 降到 8/16。四份合同有法定披露触发，规则漏识别后将其误判为“未提及”。根据这次 DEV 反馈加入覆盖检查，遇到可能受强制披露的条款且通知依据未决时保留原预测。复用同一 DEV，两路恢复到 12/16，官方证据 F1 分别从原 33.33% 和 40.63% 到 39.58% 和 43.75%。回顾性 TRAIN 使用同一检查后为 23/24 与 24/24。保留两轮及直接对照。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COMPELLED_NOTICE_20261119.json)

新增模型请求 0，核验 111 笔 TRAIN 和 32 笔固定 DEV 物理响应。连续账本 14,650 笔、在途 0，22 项检查通过。

## Revision 5 ContractNLI 副本制作条件的实测与 DEV 回放已结算

在六份原 TRAIN 合同上，固定三字段与合成两关系接收完整原文和相同条款组。两种接口在 27 个局部状态上保持同一消费者输出。12 笔请求均正常结束且格式有效。固定接口的局部读数全空；合成接口识别出禁止拍摄条款，也把逆向工程和销毁现存副本的条款读成制作限制。两路均未对任何一份合同作出完整判断。共用条款的直接对照答对 4/6。

在 24 份原 TRAIN 合同上，同一直接规则将普通教师和 PARSE 分别从 10/24 提至 18/24。规则原样应用到固定 B8 DEV，普通教师由 6/16 到 9/16、PARSE 由 5/16 到 8/16，配对 95% 区间均为 [−6.25, 43.75] 个百分点。保留直接对照，未采纳新接口。新增 12 笔 Qwen、31,985 tokens，教师 0；连续账本 14,650 笔、在途 0，18 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COPY_SCOPE_20261119.json)

## Revision 5 ContractNLI 分途径核对标记条件已结算

复用了六笔原程序响应和八笔原固定／合成接口响应。把书面与口头条件分别连回定义，并用两种接口穷举验证九个局部状态。原合成读者在已核合同中把两种各自要求标记的披露方式读成可免标记；直接逐途径核对恢复了正确判断及全部参考引文。

在六份原 TRAIN 合同上，原程序、旧直接规则与按途径绑定的直接规则分别答对 2、4、5 份。新直接规则与六份独立源审结论一致。唯一原生标签分歧来自一份广义定义，参考标签为“未提及”。四份较晚批次原 TRAIN 上，三路分别答对 1、2、3 份。归档读数与直接核对已结算，合成接口只做了离线等价验证。新增模型请求 0，连续账本 14,638 笔，在途 0，17 项检查通过。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DESIGNATION_ROUTES_20261119.json)

## Revision 5 OpenExempt 所有权候选的局部回放已结算

在原四份 TRAIN 来源上核验 40 笔原生响应和四笔有类型的分配读数。把两路提案同样限制到原文已绑定但所有权未确立的资产，保护其他资产的原预测。首轮共享反馈提案只需新增一项引文即可保留 EC F1 的 27.50%→35.83%；独立反馈仍为 27.50%。该资产在 EC 原文中没有确立所有权，基准标注匹配也不足以证明适用。原局部分配读数与 2/16 种独立补全及 0/2 种共享解释相容，保留拒绝决定。两路局部 EV 均为 40.42%→44.58%，仅用公开估值约束原输出可逐来源复现相同 F1，四份中三份的完整 EV 输出也相同。

直接估值对照只下调超出资产明示估值的唯一辖区内索赔。原 32 份 TRAIN 的可评分结果中，普通教师为 15.85%→20.38%（31 份），PARSE 为 15.06%→17.88%（32 份）。固定 B8 DEV 的 16 份均可评分，普通教师为 44.37%→49.50%，PARSE 为 42.08%→44.31%，配对 95% 区间分别为 [1.04, 10.71] 和 [0.00, 5.83] 个百分点。保留为同信息直接对照及开发证据。新增请求 0，连续账本 14,638 笔、在途 0，37 项检查通过。原冻结协议、72 份源码、TEST 终态及曝光回执已校验。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_SCOPED_POLICY_REPLAY_20261119.json)

## Revision 5 MAUD 契约前导条件的直接回放已结算

在原 24 份 MAUD TRAIN 和固定 B8 DEV 的 16 份合同上核验 68 笔归档物理响应。把同一节选中的普通经营义务和负面契约按各自前导条件区分。只在疫情措辞全部属于已分开的普通经营分项时移除对负面契约的肯定判断。原 TRAIN 的覆盖案原已正确，固定 B8 DEV 两路均由 9/16 到 10/16。

随后根据两项原 TRAIN 漏判，增加对负面契约前导条件中明确疫情例外的判定，保留未决的嵌套例外。两路 TRAIN 均由 20/24 到 22/24。在同一组固定 B8 DEV 的追加回放中，两路均为 11/16，比原结果各多两项正确判断，配对 95% 区间为 [0.00, 31.25] 个百分点。两项增益都可由直接核对原条款复现。同一 DEV 已用于两次分析，保留第一轮结果和原冻结成绩。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_SECTION_SCOPE_20261119.json)

新增请求 0，账本 14,638 笔、在途 0，27 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。两项剩余 TRAIN 误差分别是已定位的原响应截断和嵌套例外的作用域分歧。后续比较保留这一直接对照。

## Revision 5 MAUD B6/B8 旁路疫情词的配对诊断已结算

复用六笔原请求。原 B6 一份普通经营条款明示疫情措施，普通教师候选将 No 正确改为 Yes。另两份 B6/B8 合同的疫情词只出现在负面契约节选，PARSE 进入程序仍把普通经营问题答为 Yes，两项采纳候选均改为 No，六笔原响应均正常结束。

对后两份合同保持普通经营和知悉标准节选逐字相同，固定执行器、提示和响应契约，只在负面契约节选做遮蔽。疫情词遮蔽及等宽无关词遮蔽各两笔，输入 token 数分别相差 1 和 7。普通经营原答案、等宽对照、疫情词遮蔽、原采纳候选分别答对 0/2、0/2、2/2、2/2。B8「已收到书面通知」的知悉标准在两种遮蔽下均保留原错误，原采纳候选答对。改过的负面契约输出未计分。结果定位了两案的输入干扰，原采纳决定保留。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_SIBLING_CUE_20261119.json)

新增四笔 Qwen、36,001 tokens，教师 0，账本 14,638 笔、在途 0，23 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。后续把完整的任务局部输入作为同信息对照，并单独复核已收通知的定义范围。

## Revision 5 MAUD B4 空证据字段的同条件比较已结算

B4 两路采纳的 MAUD 候选均从 4/9 到 6/9。复用九笔归档读数追到同一笔进入程序的截断响应，其在必为空的证据数组内生成了 16,346 个尾随空白字符。比较两种无损表示，保留字段并固定为空数组，以及省略字段并在解码时补回。两路保留原用户输入及冻结执行器配置，穷举校验全部八种原生标签组合。六笔新响应全部完成，两路逐题相同，均为 6/9，并逐题复现两项原采纳候选的标签。两份原先正常完成的合同仍合计答对 4/6。该批两项原生增益可由共用输出恢复复现。

ContractNLI TRAIN 的范围补核确认，B1 有限制交易讨论的分项，B4 有限制联系交易相关方的分项，二者各有独立的人员招揽禁止。B3 的接触限制另有陪同前提。这些条款未支持把与引荐联系人交易的限制并入已封存的招揽规则。保留同信息直接对照和原采纳决定。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_ZERO_EVIDENCE_20261119.json)

新增六笔 Qwen、35,877 tokens，教师 0，账本 14,634 笔、在途 0，22 项相关检查通过。首次启动在缺少账本客户端导入时报错，修正前未派发请求。原冻结协议、72 份执行源码、TEST 终态与曝光回执已校验。后续区分 MAUD B6/B8 正向提案中的询问义务、已收到书面通知与输出恢复。

## Revision 5 ContractNLI 招揽限制的 TRAIN 与固定 DEV 已结算

核验 60 笔 TRAIN 与 32 笔固定 B8 DEV 物理响应。原 B4 PARSE 候选及正确输入下的 B5 补跑合计覆盖 15 份 TRAIN 合同，招揽限制正确数由 6/15 到 10/15，两路均识别四份明示禁止。24 份原 TRAIN 上，逐条规则与跨条款规则均为 24/24。跨条款仅在一份合同把受限人员定义和分项禁止接起来，证据 F1 比逐条规则高 1.28 个百分点。

封存的 TRAIN 规则应用到原 B8 DEV，普通教师由 8/16 到 14/16，PARSE 由 11/16 到 14/16，逐条和跨条款输出完全一致。普通教师配对准确率差的 95% 区间为 [12.50, 62.50] 个百分点，PARSE 为 [−6.25, 43.75]。PARSE 的三个原生正例有一项被词法范围排除，参考证据限制与引荐联系人交易。该 DEV 个例在 TRAIN 规则封存后查阅。原 TRAIN 只找到一份有不同前提的限制接触条款，保留两种义务的区别。保留同信息直接对照，原采纳决定保留。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_NONSOLICITATION_20261119.json)

新增请求 0，账本 14,628 笔、在途 0，20 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_CNI_nonsolicitation_terminal_20261119.json`。

## Revision 5 ContractNLI 按假设限定更新的前向比较已结算

复用 B4 被拒绝的 PARSE 候选及 27 笔已核验的归档读数。B1–B3 回归集上完整候选净减 10 项原生正确判断，员工披露净增 1 项，是唯一正向假设。B4 拟合集相应净增 9、2 项。封存员工披露路由后，对固定 B5 的三份原 TRAIN 合同运行候选，配对复用 B5 更新前的进入程序。

B5 的 51 项原生判断中，进入程序、完整候选、按假设路由分别正确 35、38、36 项。限定路由新增的正确标签引用了使用及复制条款，未佐证员工披露。源文核验拒绝该替换，保留了另一处有支撑的证据缩减，与逐条直接规则同为 35/51，员工披露证据 F1 为 38.89%（进入程序 34.34%）。完整候选的三项净增均由招揽限制假设的“未提及”修正解释，员工与第三方披露各变动 +1、−1。保留原更新决定。下一项核验须同时包含真实招揽禁止和未规定的原 TRAIN 合同，并保留同信息直接对照。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_SCOPED_UPDATE_20261119.json)

正式比较三笔 Qwen、34,542 tokens。首次回放跳过了原输入中的逐句编号文本，三笔、22,933 tokens 单独记账，排除于同条件结果。补跑逐笔对齐实际请求。账本 14,628 笔、在途 0，教师 0，18 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。

## Revision 5 ContractNLI 披露许可与限制的同条件比较已结算

在四份原 TRAIN 合同上比较固定字段和按消费者依赖合成的接口。两路接收相同整份合同及原生问题，复用同一解码器，并通过 729 个声明状态的等价检查。原程序、固定字段、合成接口、源审直接对照的两项原生任务合计正确数为 2/8、2/8、3/8、8/8，官方证据 F1 为 20.83%、27.08%、36.81%、91.67%。合成相对固定的配对准确率差为 12.50 个百分点，四母来源区间为 [−25.00, 50.00]。直接对照由这四份合同的逐条源审给出，属于同源回顾性结果。

合成接口改善了协议存在披露限制的判定（0/4→2/4），第三方许可下降（2/4→1/4）。它在原 B8 的一份合同引用了正确的具体限制，同时漏掉同份合同对外部顾问的许可。两路仍有引文只涉及权利授予或不同的披露对象。保留固定与同信息直接对照，原轮次采纳决定保留。新增八笔 Qwen、48,916 tokens，教师请求 0。账本 14,622 笔、在途 0，18 项相关检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执已校验。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_SIGNED_SCOPE_20261119.json)

## Revision 5 ContractNLI 披露对象与例外作用域已复核

在原 24 份 TRAIN 合同上复用并核验 45 笔原始执行响应。对“协议的存在或谈判事实不得披露”这一原生假设，进入程序、直接明示对象规则、加入定义与例外作用域的规则分别答对 9、10、10 份，官方证据 F1 分别为 29.17%、40.28%、41.27%。跨条款链接只额外补齐了一份合同的证据，增量 0.99 个百分点，配对 95% 区间为 [0.00, 2.98]。使用相同源文信息的直接规则复现该链接。

复核 B8 的具体披露例外和 B3–B5 的五项原生正向候选，原采纳决定全部保留。三份依赖语义外推的 TRAIN 合同保留原预测。后续比较需要能区分真实矛盾与未提及的整份源文依据，并能与同信息强对照区分。新增请求 0，账本 14,614 笔、在途 0，18 项检查通过。原冻结协议、72 份执行源码、TEST 终态与曝光回执均已校验。回执为 `handoff/revision5_CNI_disclosure_objects_terminal_20261119.json`。[回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DISCLOSURE_OBJECTS_20261119.json)

## Revision 5 ContractNLI 共享披露定义改名已结算

取两份已有源审的 TRAIN 合同，将被同一许可条款引用的定义名及其引用一致改名。原义务、各证据句的身份和原生请求结构保持，字符偏移与文档哈希重算。使用原 B3 候选与进入程序，复用四笔原题响应并新增四笔改名响应。员工与第三方披露合计四项原生标签，两路在原题和改名后均为 4/4；各有两项证据集合改变。

进入程序证据 F1 由 25.00% 到 43.33%，候选由 0% 到 25.00%。候选在 B3 合同由引用禁止条款改为引用许可条款，仍缺单独的成员定义。两路原题和改名读数均未给出完整的许可与定义证据。按相同原文直接链接，四项证据齐全，官方证据 F1 为 86.43%。逆向改名的同信息对照复用原题读数。原更新决定保留，结果支持区分法律标签稳定性与证据稳定性。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DEFINITION_ALIAS_20261119.json)

新增四笔 Qwen、76,355 tokens，教师请求 0，连续账本 14,614 笔、在途 0。16 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。回执为 `handoff/revision5_CNI_definition_alias_terminal_20261119.json`。

## Revision 5 M2 OpenExempt 原生冲突归因已结算

复核 B4 和 B7 两份原 TRAIN 来源的 12 笔物理响应。24 项共享上限冲突中，逐项移除一个读数都只有一种方式恢复相容。B4 的 16 项均须移除第一份编辑读数，B7 的 8 项均须移除原生分歧选出的编辑读数。保留原始输出时，其余实测读数仍有共同上限。直接上限公式和共享枚举的归因相同。

先封存去除辖区外及非法金额后的四路原题预测，再读取原 TRAIN 标注。对所有冲突一律删除原题对应索赔，删除 20 项预测，其中 7 项与原标注完全匹配，四组中三组官方 EV F1 下降。只在原读数为唯一不相容读数时删项，四组的输出逐项等于同信息的本地筛选。保留原库和采纳记录。现有 OpenExempt 金额编辑证据只定位到编辑响应，后续应寻找原任务上的直接变化，避免用这些冲突惩罚原题。[重放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_CONFLICT_LOCALIZATION_20261119.json)

新增请求 0，连续账本 14,610 笔、在途 0，24 项相关检查通过。原冻结协议、72 份源码、TEST 终态及曝光回执均已校验。回执为 `handoff/revision5_OE_conflict_localization_terminal_20261119.json`。

## Revision 5 M2 OpenExempt B7 同预算选例已结算

以 B4 已结算结果作为校准，在另一份原 B7 TRAIN 来源上封存两条选例规则。两路共用三件资产的原披露句、合法编辑池及进入程序和候选的两个原始 EV 读数。按句内后续资产数选择第一处金额，按原生引文分歧及金额选择第二处。每路两笔请求。原请求字段和响应结构逐笔复核，金额编辑同时更新同源公开资产索引。

四个共同辖区内资产－引文位置全部可比。句首编辑两路均无冲突。原生分歧编辑在进入程序发现一处未改资产的冲突，候选在这四处兼容。扩到各路全部正额位置，原生分歧编辑发现进入程序 6 处、候选 2 处冲突。共享枚举与同信息直接检查一致。B4 回顾性核对中两条规则选中同一有效编辑，B7 前向比较推翻句首先验。原 B7 更新决定保留。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_EDIT_ACQUISITION_20261119.json)

新增 4 笔 Qwen、44,154 tokens，教师请求 0。连续账本 14,610 笔、在途 0，21 项检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执均已校验。回执为 `handoff/revision5_OE_edit_acquisition_terminal_20261119.json`。

## Revision 5 M2 OpenExempt B4 原生金额编辑已结算

复用同一 B4 TRAIN 母来源的两笔原始 EV 响应。对同一句中两件所有权未确立的资产各做一次独立的一美元编辑。保留原请求系统提示、模型参数、响应结构和其余原文。新增四笔原生请求均有效，两件资产在六个响应中都有明示输出。

单独检查资产金额上限，两路均无违规。共享分配上限在进入程序的 16 个辖区内正额位置发现 14 项冲突，在候选的 4 个位置发现 2 项。两路共有的 4 个位置分别有 4 项和 2 项冲突。所有冲突均由第一种编辑触发，第二种编辑两路均兼容。共享枚举和同信息直接上限检查逐项相同，原 B4 因无源文支持的所有权断言拒绝候选的决定保留。本轮没有编辑题原生标注分数。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_NATIVE_AMOUNT_EDITS_20261119.json)

四笔 Qwen 共 32,837 tokens，教师请求 0。汇总中的零计数错误已用保存的物理响应离线结算，未重发。账本 14,606 笔、在途 0，19 项检查通过。原冻结协议、72 份执行源码、TEST 终态及曝光回执通过校验。终态为 `handoff/revision5_OE_native_amount_edits_terminal_20261119.json`。

## Revision 5 M2 OpenExempt 源文选例和跨任务作用域已核对

复核 B3、B4、B7、B8 的 64 笔原生执行响应。其中 9 个同批 TRAIN 母来源有正向候选收益，原选例语法只覆盖 1 个。按公开渲染模板，逐位置复核申报人、未确立所有权及金额，得到 24 个可实现的单金额编辑，覆盖 7 个正向母来源。每个编辑只改一个金额，原资产、其余金额和所有权状态均保持。编辑的共享解释允许两种签名，逐例补全允许四种。候选组尚无模型读数。

B7 候选的两条冲突仍成立，因为 EC 源文确立所有权。B8 若沿用不区分所有权证据的跨任务蕴含，会给候选和进入程序各标出四条冲突。四个位置均为 EC 未确立、EV 已确立所有权，按各视图允许的补全均可解释。共享枚举与同信息直接检查在 81 个状态上一致。下一步选例应利用本批已观察到的候选错因，并在新读数前登记能区分更新选择的预期，保留旧证据和直接对照。[聚合证据](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_M2_SOURCE_PLACEMENT_20261119.json)

新增请求 0，连续账本 14,602 笔、在途 0，24 项相关检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_OE_M2_source_placement_terminal_20261119.json`。

## Revision 5 OpenExempt 宾州原 B8 DEV 比较已结算

从 46 个固定公开渲染模板绑定申报人、资产组及所有权状态。八个原 TRAIN 视图的所有权状态逐项复现，原 B8 DEV 五份宾州来源的 10 个视图全部覆盖。七个资产组的所有权留作未知。固定字段对照与关系接口共用原文、资产索引、所有权和同一消费者。两路均由程序推导个人非营业财产字段。

原生 EV F1 为固定字段 68.25%、关系接口 57.46%，关系接口差值 −10.79 个百分点，五母来源配对区间 [−20.95, −1.90]。EC 为 77.40% 和 76.44%，源审后两臂均为 77.40%。固定字段 10 个视图的原生分数均与纯源审执行相同，输出完整一致 9 个。原 TRAIN 的字面词项控制每类只能覆盖 1/14 个资产，保留其结果用于说明适用范围。继续采用共用所有权锚定，当前形态接口缺少扩展依据。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_SCOPED_FORMS_DEV_20261119.json)

新增 20 笔 Qwen、123,613 tokens，教师请求 0，连续账本 14,602 笔、在途 0。14 项相关检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。回执为 `handoff/revision5_OE_scoped_forms_DEV_terminal_20261119.json`。

## Revision 5 OpenExempt 宾州资产形态关系已结算

使用已源审的全部四份宾州 TRAIN，共八个 EC/EV 视图。两个读器接收相同原文、资产索引和源文锚定的所有权状态，并使用同一个消费者。关系接口用资产形态的可能集合约束有形财产与服装两项判断。21 组可能状态经验证，未确立所有权时保留两个合法补全。[结果表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_SCOPED_FORMS_20261119.json)

源审后，固定字段与关系接口的 EC F1 为 61.13% 和 60.24%，EV 为 36.61% 和 76.61%。EV 的配对提升为 40.00 个百分点，四母来源重采样区间为 [1.79, 78.21]。回顾性词项规则在同一输入上复现了全部 24 条源审字段组，EC 为 74.82%、EV 为 82.86%。原 B8 DEV 五份宾州来源的两类视图均有可解析资产，当前所有权锚定规则每类只覆盖一份，且其资产词项均未被 TRAIN 规则覆盖。本次只检查了 DEV 公开输入，下一步应先补齐公开渲染模板的所有权证据，两臂共用。

新增 16 笔 Qwen、99,151 tokens，教师请求 0，连续账本 14,582 笔、在途 0。10 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执已校验。回执为 `handoff/revision5_OE_scoped_forms_terminal_20261119.json`。

## Revision 5 OpenExempt 资产锚定与逐项输出已结算

同源回放三份 TRAIN 的 18 笔实际读数。把带估价尾语的资产名与原文对齐，在四个视图恢复八条资产绑定。再保留所有可行补全均支持的引用和值。两项单独应用均未改变得分，联合应用改善三个视图。另有两笔 EV 因引文开头冠词大小写被整份拒绝，用指定原文单元内唯一逐字匹配恢复后，固定记录多改善一个视图。逐项穷举与同信息直接控制吻合。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_CLAIM_PROJECTION_20261119.json)

固定记录平均官方 F1 由 38.89% 提至 EC 63.89%、EV 68.89%。合成记录仍为 EC 16.67%、EV 38.89%。四处改善集中于同一 TRAIN 母来源。源审只屏蔽不受支持的读数，合成记录在该来源的资产分类仍为空。后续候选须提供可源审且能改变原生输出的分类绑定，才值得与同信息固定格式做新的真实比较。

新增请求 0，账本 14,566 笔、在途 0。17 项相关检查通过，原冻结协议、72 份执行源码、TEST 终态与曝光回执均已校验。结算入口为 `handoff/revision5_OE_claim_projection_terminal_20261119.json`。

## Revision 5 Airline 免费行李额度分配已结算

按原公开费率表编译各舱位、线路及行李额度。先按每件行李的超重与超尺寸费取较大值，再按使用免费额度节省的实际费用分配。用同一事实的穷举分配作为强对照，结果逐题一致。原 24 份 TRAIN 中，进入程序、输入顺序、仅按超重减免排序和联合分配分别答对 7、18、21、24 份。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_AIRLINE_ALLOWANCE_20261119.json)

封存 TRAIN 规则在原 B8 DEV 的 16 份留存预测上复核。15 份落在已编译线路范围内，另一份沿用原预测。原进入程序、输入顺序、仅按超重减免排序和联合分配分别为 2/16、11/16、13/16 和 15/16。联合分配相对输入顺序提高 25.00 个百分点，母来源配对区间 [6.25, 50.00]。七份 TRAIN 可以只交换托运行李位置，使按输入顺序分配的费用变化 70 美元，而最小费用保持。改序签名来自已固定规则，尚无改序后的实际读数。当前有共用计算改进的证据，M2 的独立收益仍待建立。

复用 24 笔 TRAIN 和 16 笔 DEV 实际响应，新增请求 0。账本共 14,566 笔、在途 0，19 项检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。

## Revision 5 M1 ContractNLI 独立开发与第三方取得已结算

核对原 24 份 TRAIN 合同的进入程序。独立开发与第三方取得分别答对 13/24、19/24。新配对覆盖六份原合同，区分限定于披露前的开发、分项中“预先持有”与“随时独立开发”的并列、双路径例外以及书面证明条件。固定和合成读器共用合同全文和证据索引，两个输出在 729 个声明状态上保持消费者等价。[比较结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_INDEPENDENT_ROUTES_20261119.json)

在两项原生假设合计 12 个判定中，进入程序答对 10 项，固定和合成各答对 2 项。固定读器全部判为未提及。合成读器识别出一项第三方取得，但只引了分项，缺少管辖该分项的例外条款。回顾性直接规则从同一全文链接例外引导语与分项、核对时间及来源条件，12 项均与源审及原标注一致。本次比较未建立合成接口的独立原生收益。

会话 80796 已结算。新增 12 笔 Qwen 请求、52,186 tokens，教师请求 0。账本共 14,566 笔、在途 0，21 项相关检查通过。原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。

## Revision 5 M1 Diversity B8 DEV 同信息对照已结算

用原 TRAIN 的金额解析规则回放 B8 DEV 的 16 笔实际合成接口读数，逐笔核对原始输入、选型回执及执行结果。原路线全部保留固定州籍坐标，金额用合成关系。16 份州籍读数均与原文一致，两个同一当事人对的合计读错。只从原引用提取金额，保留原州籍读数，原生正确数由 14/16 到 16/16。普通和 PARSE 式模型对照均为 9/16。[对照结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_DIVERSITY_DEV_LITERAL_20261119.json)

把相同原文州籍及金额分别编码到固定和合成消费者，两路均为 16/16，原生答案和两个中间判定逐题相同。金额修复相对原合成路线的平衡准确率差为 +12.50 个百分点，分层配对区间为 [0.00, 31.25]。本结果限于已有 DEV 的受支持句法；已冻结 TEST 的原比较继续按其原对照解释。

新增请求 0，连续账本 14,554 笔、在途 0。8 项 Diversity 和消费者检查通过。另一个旧 RR 检查缺少其既有 TRAIN fixture。原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。

## Revision 5 M2 ContractNLI 口头信息定义回放已结算

核对 B3 和 B4 的两笔原始教师请求、更新决定及两臂保存的程序。教师收到当批原生汇总；当时该假设未接入关系筛选。B3 整体分类提高 2/153，同时新增两处有源文支持的口头信息漏判。B4 恢复这两处，但其全前缀口头信息分类由 9/12 降至 7/12。共享、逐例与同信息直接核查对已确认的正向源文证据作出相同判定。[回放结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_ORAL_SCOPE_20261119.json)

开发版用同一原文验证定义、分项及所涉披露主体，保留无充分证据的原判定。用 B3 留存读数回放，口头信息答对 7/9，同句核查 8/9，跨条款核查 9/9。后续 12 份 TRAIN 的分类均为 11/12，答错计零的证据 F1 依次为 65.28%、73.61% 和 83.33%。使用同一封存规则复核原 B8 DEV 的 16 份合同，规则命中两份，跨条款与同句结果完全一致。普通臂分类为 14/16，PARSE 式臂为 10/16→11/16。两臂答错计零的证据 F1 分别变化 +0.42 和 +2.50 个百分点，配对区间均包含零。口头信息子任务的句法覆盖是目前可验证的共用修复。

复用 45 笔 TRAIN 和 32 笔 DEV 执行响应，新增请求 0。连续账本 14,554 笔、在途 0。25 项相关检查通过，原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。

## Revision 5 M1 ContractNLI 明示标记条件已结算

核对原 24 份 TRAIN 合同及对应物理请求。进入程序全部判为“所有保密信息须由披露方明确标记”，答对 5/24。六份定向比较覆盖强制识别、性质认定、明示无需标记和副本标记等结构。固定坐标和合成关系使用同一合同全文和原生证据索引，逐一验证 27 个声明状态的消费者等价。[配对结果](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_DESIGNATION_20261119.json)

固定坐标六次都把两个局部字段留空，同时断言普遍标记要求，原生答对 0/6。仅采纳该普遍断言也只能答对 1/6。合成关系答对 1/6，抓到了明示无需标记的条款，但也把另一案中的书面标记与口头确认条件读成豁免。在全部 24 份合同上，回顾性字面规则覆盖五份并全部答对。副本标记一案的原文源审与标注口径分别保留。当前结果未建立合成接口相对同信息强对照的独立收益。

会话 48056 已结算，新增 12 笔 Qwen 请求、50,969 tokens，教师请求 0。连续账本共 14,554 笔、在途 0。21 项检查通过，原冻结协议、72 份执行源码、TEST 终态和曝光回执均已校验。

## Revision 5 M1 OpenExempt 逐件部分执行已结算

三份原 TRAIN 来源的 18 笔留存请求均与物理账本和原始输入匹配，14 笔通过既有 v2 解码器。独立开发版本对固定和合成接口共用原文资产绑定与源审，只保留能在未决布尔输入的全部补全下保持不变的逐件输出。源审用于撤下无证据断言，原读数缺失的属性仍保留未知。预测封存后用原 TRAIN 评分。[比较表与复现入口](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ASSET_PROJECTION_20261119.json)

经同一源审核查，整案执行全部弃答。逐件执行下，固定记录的 EC 和 EV 平均 F1 均为 38.89%，合成记录分别为 16.67% 和 38.89%，固定列式两项均为 16.67%。固定和合成记录在六个视图中的五个输出相同。另一份 EC 视图中，固定记录多恢复两件资产。该结果将可恢复的分数归因于两路共用的逐件执行。源审仍是这项回顾性比较的输入，当前两项贡献的独立收益尚未建立。

新增请求 0，连续账本 14,542 笔、在途 0。32 项检查通过，原冻结协议、72 份执行源码、TEST 终态与曝光回执均已校验。

## Revision 5 M2 MAUD 嵌套例外累积核对已结算

在原 TRAIN 母合同和模型摘录中，分别核实了贷款修改的“不构成违反”说明、临时网点关闭的明确例外，并将后者另节的访问限制排除在该作用域外。B6 晋级的普通程序和 PARSE 式程序各沿用同一版本与读取契约。两路在 B6 贷款项均答 `No`，在 B8 网点项均答 `Yes`。复用四笔物理响应，逐笔校验输入与版本。原生参考均为 `No`。[累积核对](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_NESTED_EXCEPTION_JOIN_20261119.json)

当候选口径仅有“所有单项豁免均计入”和“仅计主条款层级的豁免”时，两路单独读数均可成立，累积均无共同解释。相同信息的相等检查在九种已答与缺测组合中等价。加入“计入明确单项例外、保留不构成违反的说明为另一类”的措辞口径后，两路读数均可由同一口径解释。已查阅的 MAUD 原论文和版本发布说明未给出这两种写法的标注取舍。现有证据仅在前两个候选口径下支持拒绝。[MAUD 原论文](https://aclanthology.org/2023.emnlp-main.1019/) · [版本发布记录](https://zenodo.org/records/7500064)

新增请求 0，账本 14,542 笔、在途 0。31 项检查通过，原冻结协议、72 份源码、TEST 终态和曝光回执均已核验。

## Revision 5 MAUD 母合同定义覆盖核对已结算

逐份匹配原 24 份 TRAIN 母合同的字节哈希，核对 24 笔留存响应。六份摘录引用了可定位的普通经营定义。其中一份停在定义的分号，母合同紧接着明确把符合条件的疫情应对认定为普通经营。只恢复该段并按原条款所用的定义解释，原程序的一项 `No` 可由同信息的直接规则恢复为参考答案 `Yes`。原输入与清单保持原样。[母合同核验](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_PARENT_DEFINITION_COVERAGE_20261119.json)

在原 48 项 TRAIN 契约问题上，原留存程序答对 41 项，任意位置关键词诊断为 44 项；用已核对的定义和作用域做回顾性直接重放为 46 项。剩余两项参考差异都涉及禁限条款内的具体贷款或设施例外，官方标签均为 `No`，未用标签扩展或收窄源文语义。新增模型请求 0，账本 14,542 笔、在途 0。17 项检查通过，原冻结协议、72 份源码、TEST 终态及曝光回执均已核验。

## Revision 5 M2 跨组累积证据审计已结算

在此前 16 条验证记录上补入 19 条早期 TRAIN 验证，核对 35 条记录、82 笔去重物理响应及其原始请求。其中 17 条伴随正向原生候选得分。按候选、语义定义、源审、解释域和读取契约归并，有三组重复记录，每组都已有一次验证覆盖合并后的全部响应。三组的拒绝都已在单组出现，累积未增加拒绝。保留相同语义但允许不同读取契约的诊断也没有出现只在累积后才发现的冲突。[审计表](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_CUMULATIVE_AUDIT_20261119.json)

35 条记录的完整允许签名均可由二元投影重建，二元与联合检查对已存实际读数的判定全部相同。相同候选与参考实现之间另有六对记录的语义作用域不一致，不能直接合并。新增模型请求 0，连续账本 14,542 笔、在途 0。17 项检查通过，原冻结协议、72 份源码、TEST 终态和曝光回执已核验。

## Revision 5 M2 ContractNLI 返还与留存共享筛选已结算

用七份原 TRAIN 合同分别核实终止返还义务与处置后的留存条款。核对 B3–B5 的五个本批原生正收益提案、31 笔去重的实际响应和三批的归档执行源码。原流程采纳三个提案。B5 的 PARSE 式提案当批分类增益为 5.88 个百分点，先前 TRAIN 增益为 2.45 个百分点；在一份原文禁止留存的合同上，它新增了留存许可断言。只拒绝新增冲突的回顾性筛选会保留原程序。逐项直接核验、独立补全和共享解释在原读数及全部已知与未知组合上判定一致。[筛选重放](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_CNI_DISPOSITION_RETENTION_20261119.json)

在一份原合同中只替换明确的归档副本例外，局部留存结论改变，终止返还义务保持。同信息直接规则恢复了完整四查询签名。该构造是离线检查，未发起新请求或改动原程序选择。账本 14,542 笔、在途 0，17 项相关检查通过。原冻结协议、72 份归档源码、TEST 终态和曝光回执均已校验。两项贡献的可靠独立收益仍待建立。

## Revision 5 ContractNLI 终止触发覆盖核对已结算

逐份核对原 24 份 TRAIN 合同，复用 21 份与原文完全匹配的源审卡，复核 24 笔历史执行器响应。七份合同明确将返还或销毁义务绑定到协议或所涉关系的终止，其中三份在原图卡的义务触发边上缺少相应终止标签。此前字面规则漏掉的五份标注正例中，一份明写服务终止，可由同信息的直接规则恢复。另三份分别写交易未继续、关系未建立或目的完成，合同另列协议终止条件。最后一份的引文仅有请求触发。同属请求触发的十份原合同含一份参考标签为蕴含、九份为未提及。这些差异限定了可用于接口选择的原文证据。[覆盖审计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_TRIGGER_COVERAGE_20261119.json)

原图卡的完整性标记已保留，20 份仍为未闭合。当前没有新增候选或运行任务，连续账本 14,542 笔、在途 0。11 项相关检查通过，原冻结协议、72 份源码、TEST 终态及曝光回执通过校验。两项贡献的可靠独立收益仍待建立。

## Revision 5 M1 ContractNLI 返还与销毁义务配对已结算

原共同程序在 24 份 TRAIN 合同上均判定终止时须返还或销毁，实际答对 11/24。针对义务和终止条件分列、仅按请求触发或另有存续条款的六份原 TRAIN 合同，两路使用同一完整合同和原生证据索引。合成接口把终止条件及其是否作用于同一项义务合成一个关系，保持声明域 81 个状态的消费者输出。固定与合成各答对 3/6。将错答和弃答的证据分记为零后，平均证据 F1 分别为 17.86% 和 32.78%。原生证据 F1 为 17.86% 和 49.44%，其中 16.67 个百分点来自一份空引用弃答。合成读器在一份合同额外找到了真正受终止触发的返还条款。[配对与错因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CNI_DISPOSITION_SCOPE_20261119.json)

针对这六种已审结构构造的窄字面对照答对 6/6，证据 F1 为 88.33%。另对原 24 份 TRAIN 只扫描命中范围，未把六例结果外推。当前结果支持进一步查找超出显式同句或连续分项的作用域结构，未实现相对同信息强对照的独立收益。会话 64817 已结算，12 笔 Qwen 请求、39,901 tokens，教师调用 0。连续账本 14,542 笔、在途 0，11 项相关检查通过。原冻结协议、72 份源码、TEST 终态和曝光回执通过核验。

## Revision 5 M1 ContractNLI 跨条款证据配对已结算

按原文中的代表人定义和使用位置筛查原 24 份 TRAIN 合同，六份入组。两路读取同一完整合同和原生证据索引，均可分别引用许可条款和外部定义，消费者的 36 个声明状态逐项保持等价。固定坐标答对 0/6，证据 F1 为 16.67%。合成关系答对 5/6，证据 F1 为 37.62%，其中两份许可结论有独立源审支持。原多任务共同程序答对 6/6，证据 F1 为 58.33%。[配对结果与错因](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CNI_LINKED_EVIDENCE_20261119.json)

两份必须跨条款引用的合同中，合成读器在一份补齐两处漏引，证据 F1 从原程序的 50% 升至 85.71%。另一份两路均选错条款，把保密限制当成另节的明示许可。三份合成输出标签正确但引用不支持判定，另有一份因重复引用同一索引而拒绝解码。复查 24 份原 TRAIN 合同后，这两种已知措辞各匹配一份。按原文直接连接定义与许可的回顾性规则答对 2/2，平均证据 F1 为 90%。目前这两种措辞没有新增模型比较。[字面匹配预检](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M1_CNI_LINKED_LITERAL_PREFLIGHT_20261119.json)

会话 70296 已结算，12 笔 Qwen 请求使用 99,412 tokens，教师请求 0。定向检查 20 项通过，一项历史持久化检查因既有检查点缺少 `artifact_root` 失败。连续账本 14,530 笔、在途 0。原冻结协议、72 份源码、TEST 终态与曝光回执通过校验。

## Revision 5 M2 二元与联合筛选审计已结算

复用 16 组有真实读数的历史 TRAIN 投影，逐笔核验 45 笔去重后的物理响应。12 组伴随正向原生候选增益。每条验证记录均只有一组读数。16 组的完整签名都可以由其所有二元投影重建，二元筛选和联合筛选在留存读数上的判定全部一致。[筛选审计](../reports/legal_skill_convergence_20261117/paper/tables/REVISION5_M2_PAIRWISE_SCOPE_20261119.json)

在一份原 B7 TRAIN 来源中，两件资产的估值有原文引文，所有权均未决。只编辑一处估值，在受控的所有权条件投影中，独立补全允许 12 个签名，二元闭包允许 6 个，共享补全允许 4 个。同信息的直接换算与求和可以精确恢复这 4 个签名，因此没有新增原生比较。连续账本为 14,518 行、在途 0。本次没有新增模型请求，17 项相关检查通过。已校验原冻结协议、72 份源码、TEST 终态及曝光回执。继续实测需要可与同信息强对照产生不同选择的源文证据。两项贡献的可靠独立收益仍待建立。

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

# 当前Goal：统一方案下M1/M2实现、完整评价与论文

2026-11-18，系统 Goal 已恢复为 `active`。目标内容与方案沿用原设置。固定方案上游37a76ffdf9490d7d213f5a9e67553a174416d84c，43文件逐Git blob导入验证。原177源审、全部旧失败/结果、连续账本及曝光记录保留。

本机 Qwen3-8B 已通过只读模型卡核对，仍是同一权重路径和 32768 上下文，thinking 关闭，采样配置沿用。Codex 全局默认从 gpt-6.1-sol 变为 gpt-6.2-sol。原教师请求经 CLI 显式指定 gpt-6.1-sol/high。后续准备程序改读 `configs/legal_skill_convergence_teacher_v1.json`，冻结同一教师条件。核对未触发教师调用。

关系提示已从同一 AST 生成明确的 true、false 和 null 条件。新模板绑定读者与执行器版本，旧工作条件下的统计保留供复核。极性诊断已终结。原失败 TRAIN 来源只发出一次改写提示的本地请求，固定接口精确复用。关系接口仍在同一州籍比较上误读，原生答错。该记录否定了单靠本次提示改写修复该错误的假设。

## 完整目标

按固定统一方案及同目录配置，实现M1、M2两项法律技能进化方法，争取可归因的实际指标提升。复用已有工作，冻结Qwen3-8B、关闭thinking，保留教师和外部技能库，重点验证M1在非Airline数据上的实质作用。依据TRAIN失败与DEV反馈自主改进，允许必要重构和修复，不设优化轮次上限、不逐轮确认；有明确依据、实质改动和可检验预期就继续，无新依据不反复重跑。自主完成实现、小试、128来源8批完整训练、DEV曲线、冻结后五库分别测试、独立消融、强对照及论文初稿，不用测试标签调方法，不无限追加数据、种子或方向。只有交付齐全且两项贡献获得可靠效果证据才标记achieved，不能只交负结果报告就宣布完成；确无可实施的新改进依据时保存证据并明确目标未达成。持续推送代码、结果、成本和交接记录，沿用有效资源授权，仅关键阻断集中询问，不逐阶段等待复核。

固定执行文件：reports/legal_skill_convergence_20261117/PLAN.md、METHOD_1、METHOD_2、protocol.json、CROSS_DATASET_IMPLEMENTATION、DATA_SELECTION及REVISION_REVIEW。

## 已实现及实际证据

M1已在原residual合成器上实现多关系、身份绑定、独立源忠实性和组合生产decoder；Diversity真实来源接入、实际四候选配对学习、库保存/恢复、预先选择及另一母来源真实调用均已执行。24个TRAIN×4候选的96次参考输入贯通生产评分链，三个原生字段全部一致，是参考链证据。

首次2次真实读取均发生生产拒绝，已封存12份精确绑定源码；共同修复锚点、complete/unread互斥及相同结构化实体输入后，格式拒绝消失。在第一个Diversity-6 TRAIN母来源，固定坐标接口错误、完整联合关系正确且全部源忠实；两个混合候选错误或unknown。实际配对学习选中联合模板。第二个预选Diversity-5母来源的真实复用则相反：固定接口正确且忠实，所学关系把同州籍的比较读成true并答错，确实执行所学主路径、无fallback。两条TRAIN不支持总体收益；不能只展示首例。详见CROSS_MOTHER_REUSE_20261118.md。

M2已有共享law/root解释、合法源编辑、派生DAG、精确允许签名及跨组解释因素持久化，Diversity数量/实体编辑可独立重解析验证；该库K为单解释，shared与single控制相同，不作为共享解释优势。MAUD独立源审1次完成，58效果/59例外引文通过，但缺16项交叉引用，无经源文确认的歧义，不人为补变量。M2 选组已支持跨组累积冲突。四个固定 Diversity TRAIN 来源的受控遮蔽诊断均产生了共享可行而独立补全更宽的关系。该诊断的未知量来自人为遮蔽。后续合同作用域与自然不完备的配对实验见最新运行核验。

本轮 38 项机制、生产解码及学习库检查通过，旧45项付费响应回归和源范围检查记录保留。公开证据包离线重现10次逻辑解码、8份独立执行器响应，核对150文件hash；不需要私有账本或原始库缓存、0新请求。复现：`python -m experiments.convergence_replay_public_evidence`。

## 数据与运行状态

五库名册已锁定 TRAIN128/DEV80/TEST160，保留八个原批次并验证当前曝光冲突为零；CNI完整17项假设、MAUD固定3任务。MAUD TRAIN23/72任务扩展到语法完整section，仍不等于法律语义闭合；原177审计不能自动迁入变更输入。Diversity DEV/TEST按预定变体配额和同结构组去重隔离；MAUD整库近重复审计无新增候选冲突。TEST源文/标签未向开发代理展示、未评分，正式模型、B8 技能库及执行绑定尚待完成。

MAUD 两个局部版本均已结算。原版本固定 5/6、合成 0/6，修订为 AST 联合语法并约束 21 个可达联合输出后，固定 5/6、合成 2/6。分母是局部投影，保留长度拒绝。Diversity M2 真实比较也已结算，原方法和两条教师补丁均原生正确，均对遮蔽变体输出未知，普通与共享选择均保留原方法。OpenExempt 已从旧源审批卡构造保留原生未知所有权的金额编辑，两种共享签名、四种独立签名，后续真实模型比较与事实断言复核见 DEVELOPMENT_EVIDENCE_20261118.md。

固定 TRAIN 20 母来源共同 B0 已结算。工具会话 97558 是终态。读取 `artifacts/legal_skill_convergence_20261117/handoff/run_state.json` 和 `pilot_b0_current.json`，核实实际进程、连续账本及终态后从未完处恢复。MAUD 会话 44297 与 75498、M2 会话 60646 均已结算。各历史绑定和源码快照保留。

## 公开同步

研究分支 `research/paired-interface-structural-transfer-20261116` 已核对远端提交 `633e0e296cbfde8819a0d2c786b9cddc9bf379fa`。该次推送包括源码、测试、教师版本和汇总交接。原始读数与账本索引保存在项目内。

## 下一步

1. 用四个既定 TRAIN 母来源的同类真实错误修订 MAUD Knowledge Definition 读法。保留极性诊断负结果。下一次需验证能约束主体绑定或输出极性的实质接口改动，复用原有效 wire。模板版本已绑定，提示改动后的读数单独计入。
2. 用已结算共同 B0 的逐来源错误推进合同整题及 OpenExempt 自然未确定所有权配对验证。将仅用于诊断的关系与原生分数分开记账。
3. 固定20母来源完整小试/强对照、最终数据/共同初始化/预算绑定，继而128来源8批五臂训练、DEV曲线、B8冻结五库TEST、消融/迁移与论文。依TRAIN失败和DEV汇总持续改进，不拿TEST标签修方法，不无依据原样重跑。

Goal未完成；当前实现可运行与局部正反例不代替两项可靠贡献证据。


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

## 五库小试结算与当前会话

PARSE 补测会话 69223 已结算。固定20母来源、96项原生任务全部有结果。五库同口径母来源效用中，MAUD 从 0.6667 到 0.8333，OpenExempt 从 0.1357 到 0.2254，其余三库保留共同程序。按协议用于排名的五库等权效用为 0.5676。五次教师与24次执行器共计 86961 与 153420 tokens。当前有一个已完成的外部排名输入，尚未选定最强家族。补测的25份源码已校验归档。

紧凑普通教师汇总会话 52538 已结算，五库均保留共同程序。原会话 62245 的 OpenExempt 执行在预分词处被拒，未为该拒绝预留生成。源输入和输出 schema 均保留，纯传递程序改用共同读者输入，工具目录和共享资产留在组合阶段。冻结 tokenizer 将拒绝的读者输入从 27115 tokens 缩至同组最长 7391。三库已测读数和第四份教师提案精确复用，两个绑定各封存25份源码。五次有效教师与24次有效执行共计 88430 与 238040 tokens。

当前唯一生成会话 66228，运行固定20母来源的 SCOPE 式分解对照。绑定目录 `8f95c2fe0b65e54f190c5f68eb2652dcf79e04acbdf81a1c8f96773eb782499e`。重入先核对 `handoff/compact_teacher_scope_current.json`、实际进程和连续账本。分解测量与反例归因、回归验证分别验收。其余外部候选仍需同口径核验后才能锁定正式强对照。

五臂 DEV B0 已用原已付预测和公开费率补测重建，80 母来源和384项原生任务每臂完全一致。Airline 2/16，其余来源逐条与原评分一致。`python -m experiments.convergence_shared_dev_checkpoint` 复核原账本和封存预测，零次新生成。索引见 `handoff/common_DEV_B0_five_arm_replay_20261118.json`。这是与外部家族无关的共同检查点。正式八批训练、B1/B2/B4/B8 DEV 与冻结 TEST 仍待执行。

## 有效分解读数、归因与 M1 配对

会话 66228 已终结。SCOPE 式分解在同一20母来源上完成五教师、24执行器，计 87426 与193117 tokens。对照在 MAUD 选入 9/12 的候选，共同程序为 8/12。其余四库保留共同程序。对每库第一条测得错误的来源，从已保存的读数精确重放六个程序单元。有限标签叶干预在 CNI、Diversity 和 MAUD 改变了错误答案，属于组合归因。该归因没有引入新模型响应，独立核验的源文编辑阶段及两项回归对照的完整排名仍待完成。

M1 八批校准器读取已核验的当前批次记录，仅以可见 TRAIN 的同源候选、独立来源审阅及原生评分更新库。24 个 Diversity 母来源在固定八批中每批3个，四个候选每例共96项核对，384个局部事实与旧参考读数的编码完全一致。该验证无模型调用。其余库的正式整题适配和学习效果仍待完成。

会话 65543 已结算。24 个 TRAIN 来源的原文锚点及四个指定读数的参考生产链已核对。原两母来源的真实配对中，固定、合成各 1/2，四次共 7101 tokens。合成修复 Diversity-5 的同州籍误读，在 Diversity-6 错读四个州籍比较和两个金额关系。固定坐标在 Diversity-6 的州籍正确，两处共有主张中的第二笔金额错读，影响四个组合单元。17份绑定源码已封存。回执见 `handoff/diversity_source_binding_result_20261118.json`。后续从两个实质问题入手，独立核验名称绑定后再解码关系极性，同一原文明确共享的金额应按消费者依赖绑定至同一观察。当前无生成进程，连续账本 12742 笔、零在途，Goal 内执行器 1790742、教师 359847 tokens。

## 外部家族锁定与共有条款复用

固定20母来源上的外部家族已经一次锁定。PARSE 式优化排名效用 0.567621，SCOPE 式 0.533015，SkillEvoReg 式验证与 Synedrion 式高阶关系均 0.516349。后两者共享五个普通教师候选及24个实测读数，五库原生正向候选均为空，故未进入后置回归阶段。已有 Airline 两对同读数回归保留为机制核验。此排名覆盖四种明确的适配，不视为外部论文原实验复现，效用仅用于选择。最终锁为 `handoff/locked_external_baseline_20261118.json`。SCOPE 会话 99169 完成四份 MAUD 源文可逆角色更名，候选仍为 9/12，共同程序为 8/12，预设成对退化为零。八次执行共 73869 tokens，26份绑定源码已封存。

共有主张按同一原文条款的唯一位置分组，保留覆盖的所有当事人对，金额坐标只读一遍。24 个固定 TRAIN 来源中16个减少读取单元，核验3312个三值结果赋值及96个实际生产链参考解码。校准会话 79058 完成两个原母来源的四布局对照，合成金额关系加固定州籍 2/2 且全部源忠实，固定 1/2，完全联合 0/2。八次读数共12023 tokens。冻结该选择并排除原小试后，复用会话 62152 在同变体的两个后续母来源真实运行，固定 2/2，所学接口 0/2。两次错误都是将明确低于 75000 的金额总和判为过线。四次读数共 5934 tokens，19份及23份绑定源码已封存。校准正分和跨母来源反转同时保留。

新金额 M2 证书从该原文的两处共有主张生成合法的数值编辑。对每处有两个实际覆盖的原被告对。控制遮蔽一个金额并共享同一未知量，低额和高额签名允许三种组合，逐例独立补全允许四种。该校验没有使用原生标签或模型调用，不能计作原生 M2 效果。索引 `handoff/M2_diversity_amount_relation_preflight_20261118.json`。下一次实测应以实际读数定位低金额过线错误，将真实关系违反与原生更新分开判定。

五臂共同 B0 已绑定最终外部排名、冻结配置、128个 TRAIN 母来源及592个任务，并核查80个 DEV 母来源、160个 TEST 身份与连续账本隔离。原已付 DEV 读数完整复用，无新生成。正式 B1–B8 更新和两项贡献的独立证据仍待完成。索引 `handoff/formal_bootstrap_current.json`。当前所有实验已结算，累计账本 12762 笔、零在途，Goal 内执行器 1882568、教师 359847 tokens。TEST 原文与评分继续封存。

## 金额 M2 实测与 B1 前置观察

会话 77024 已结算。复用四个原始来源的已付读数，将同池两个冻结教师补丁与原接口比较。天然金额信息未遮蔽的原生比较均为 2/4；候选 B 修复一例同时损失一例。两种歧义编辑和已知金额足以过线的第三锚点上，三策略均给出未知，无格式错误。原生、单解释、逐例补全、共享解释四种规则均保留原接口。新增1教师和17执行器，17328及15344 tokens。36份绑定源码已封存。后续三点读数使用明确金额和原文证据，经确定性规则求下界。它针对已证实的锚点弃答，尚待实测，索引 `handoff/m2_amount_projection_current.json`。

五臂 B1 前置观察会话 52664 已结算。固定首次16母来源、74项原生任务，五臂结果一致。20个逻辑读数复用13个，新增7个，39970 tokens。B1 未从小试预装技能。26份绑定源码已封存。当前唯一有生成的会话为 33790，`handoff/formal_b1_fit_current.json`，拟合普通和 PARSE 两个对照。初次会话27605在 ContractNLI 发出执行器请求前超过上下文，原教师提案已付且原33份源码均已封存。修订仅把重复的工具元数据和固定库资产留在程序宿主；保留完整公开输入和原生 schema。使用冻结服务实测三输入 24356、9773、9886 tokens，均容纳原8192 output 配额。恢复精确复用原教师提案。M1 首批三个 Diversity 母来源的12项候选已绑定待运行。TEST 仍封存。

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

M2 重新核验了三组原生正向候选的已结算投影。遮住无原文支持的字面断言后，OpenExempt 小试和 B3 各自的 2 个共享签名全部保留。金额小试的派生判断兼容 3 个共享签名中的 1 个，原响应同时有未经原文支持的金额。因此 3 组均没有独立于原文事实检查的共享拒绝。诊断复用了实际响应，保留原更新决策。回执 `handoff/M2_signature_through_B3_20261118.json`。前一轮审计与 B4 观察状态已同步并复核公开研究分支 `15634344022b1d102f79ed63490c719c0783257e`。

M1 同语法独立对照已绑定固定小试中的四个 Diversity 母来源。离线逐源留一，在相同兼容实测候选上比较正确固定读取、静态最短 schema、仅按原生表现选择和带源忠实性选择。四个来源分布在 B2、B7、B8。B2 的四个既有读数已按账本逐个复核，B8 拟合后完成整组比较。入口 `python -m experiments.convergence_m1_pilot_controls replay`。选法已固化到 `handoff/m1_same_grammar_controls_prepared.json`，该比较使用 TRAIN。

会话 76509 在 B4 的接口拟合阶段收到 SIGTERM。原会话已退出，确认 10 笔教师和 64 笔执行器均已完成，零在途，54 份绑定文件均与原哈希一致。恢复会话 11279 复用同一绑定与已付结果，已实际继续接口拟合。见 `handoff/B4_fit_interruption_20261118.json`。研究分支最近核验至 `4787d417faada4f70ddc888669ea5e4b51fe1d34`。

B0、B1、B2 固定 DEV 曲线已渲染为矢量 PDF 和 600 dpi PNG，逐臂九项原生指标见 `dev_curve_figures/B2/`。B1/B2 的 90 个点与各自终态汇总一致。下一版由 `python3 -m experiments.convergence_plot_dev_curves --through 4` 读取结算后的 B4 DEV。

## B4 五臂封存，固定 DEV 在运行

恢复会话 11279 已正常终结。64/128 个来源已进入五臂正式训练。B4 拟合累计 72 个 Qwen、10 个教师请求，分别用 518284、175676 tokens，54 份绑定文件已按哈希归档。SIGTERM 后仅补发尚未开始的 8 个接口读数。两个含 M1 的臂各保存 48 个实测候选读数。见 `handoff/B4_training_terminal_audit_20261118.json`。

普通教师采纳 ContractNLI、MAUD 和 OpenExempt。ContractNLI 当批 21/51→25/51，前三批 78/153→81/153。其证据 F1 当批 0.28758→0.28105，前三批 0.24566→0.29699。PARSE 的 ContractNLI 候选当批净增 9/51，前三批净减 10/153，保留原程序。两臂的 MAUD 候选均在当批净增 2/9。OpenExempt 普通候选当批效用增加 0.021537，相对 M2 旧程序增加 0.028981。它在两个只说明占有的原文变体上断言无所有权，并遗漏明示金额。三种解释兼容检查均通过，字面事实检查拒绝，M2 保留原程序。四组实际原生正提案仍无单独由共享解释导致的拒绝。回执 `handoff/M2_signature_through_B4_20261118.json`。

M1 时间顺序离线核验已延伸至 B4 的九个固定来源。普通 7/9，现行规则 6/9，替代规则 5/9。两套规则在新增的三个来源均运行普通程序。继续保留现行选择。见 `handoff/M1_incumbent_through_B4_20261118.json`。

当前唯一生成会话 3504，从 `handoff/formal_B4_DEV_current.json` 恢复。它绑定已封存五臂 B4 和固定 80 个 DEV 来源。运行完毕后核对账本、五臂终态、绑定和分库效果，再画 B4 曲线并续跑 B5。B8 前 TEST 保持封存，Goal active。

## B4 DEV 期间的 TRAIN 核验

M1 复核了 48 条已付候选读取。24 条所有局部关系均通过独立源审。遮蔽不受支持的局部读数后，33 条在原消费者下保持相同且确定的原生输出，其中新增的 9 条原生正确。以该充分支持条件重新按时间顺序选读器，九个后续固定 TRAIN 来源的路由均未改变，现行与替代规则均为 6/9。保留现行规则。回执 `handoff/M1_consumer_support_through_B4_20261118.json`。

B4 的两条 OpenExempt 投影实测同时携带原生任务映射指令与局部 JSON 指令，均错判所有权并遗漏明示金额。新的配对诊断使用唯一的投影输出指令，按原文引文核验资产与金额，并新增受所有权约束的局部金额。在同一原文及金额变体上，独立补全允许 4 种派生组合，共享所有权允许 2 种。诊断只使用固定 20 例中的原母来源及该金额变体，比较 B4 原候选和原 M2 进入程序，复用正式 B4 的原生对比。准备完成，尚无新模型读数。见 `handoff/m2_oe_title_value_current.json`。60 项定向测试通过。

B5 的 16 个母来源、74 个原生任务已绑定五臂 B4 快照。入口 `handoff/formal_B5_observe_current.json` 处于 prepared，当前仍由 B4 DEV 占用唯一生成会话。所有拟合和诊断继续保留 TEST 隔离。

## OpenExempt 投影诊断结算，B4 DEV 已续跑

会话 99670 的四笔 TRAIN 投影已结算，新增 24355 个执行器 tokens，零新增教师或原生任务调用，56 份绑定文件已归档。候选在两变体均逐字定位金额并保留所有权未知，派生金额均为 0。独立补全、单一解释和共享解释三路选择相同。原 M2 程序也读对两个金额，但第一变体断言了无支持的所有权，把对应明示金额计入，第二变体计 0。遮蔽字面断言后，原程序实际的派生量兼容 4 种独立签名中的 1 种，兼容共享签名 0/2。该诊断定位了可实测的共享矛盾。原程序同时违反事实检查，且候选为两个零，实测未产生可独立归因的共享更新效果。保留 B4 快照。签名和账本核验见 `handoff/M2_title_value_signal_audit_20261118.json`。

B4 DEV 原会话 3504 在请求边界结束，17 个已付响应全部结算。首次换接会话 86060 发现运行时把未发出请求的暂停结果留作普通缓存。核实对应 ID 在账本和物理请求区均不存在后，归档该单一结果文件。会话 17651 在原绑定上恢复，原未发请求已实际完成。B4 DEV 唯一生成会话为 17651，按 `handoff/run_state.json` 和实际进程续跑。B5 仍已准备。TEST 封存，Goal active。

## B4 DEV 四臂结果与 M2 交叉诊断

B4 的普通教师、仅 M1、仅 M2、双机制四臂均已各封存 80 个 DEV 母来源和 384 个原生任务。Diversity 上两个 M1 臂为 14/16，各自对照 9/16，平衡准确率配对增量 0.3125，95% 母来源分层区间 [0.0625, 0.5625]。16 个均实际运行合成接口，6 个修复全部通过逐关系源审，1 个退化。OpenExempt 保留旧程序的两臂相对匹配对照，EC F1 0.17086→0.25083，配对增量 0.07996 [0.00539, 0.16039]；EV F1 增量 0.00634 [−0.02947, 0.03999]。程序保留源于字面事实检查。回执 `handoff/B4_M1_DEV_two_arm_seal_20261118.json`、`handoff/B4_OE_DEV_four_arm_audit_20261118.json`。PARSE 臂继续运行，五臂终态和曲线尚待结算。

会话 68045 结算 8 笔 OpenExempt TRAIN 交叉投影，合计 48500 tokens，57 个绑定文件已归档。两套程序各读对 4/4 明示金额。候选 0/4 引文通过原文核验，3 次无支持的所有权断言，旧程序分别为 4/4 和 4 次。两套程序各有 2 个独立补全签名与 0 个共享签名兼容其派生量，计入实际字面错误后没有独立归因的共享选择差。回执 `handoff/M2_title_partition_signal_audit_20261118.json`。下一项短诊断已准备，将来自独立源审且所有权仍未知的 K 等量提供给两套程序，使模型只读派生量；该部署尚无新读数。

会话 17651 在外部对照请求边界退出，77 笔 B4 DEV 结算全部保留，代码和已封存预测保持原绑定。唯一生成会话为 55236，继续同一 PARSE 臂。`convergence_eval_cost_audit` 已在 B1 和 B2 原封存件复算通过，按臂和数据集核对实付请求、tokens、耗时及结束类型，按实际响应 ID 去重。61 项定向测试通过。B5 观察仍在 prepared 状态。

## B4 DEV 五臂结算，B5 已开始

会话 55236 正常终结。五臂各 80 个 DEV 母来源、384 个原生任务均封存，58 份绑定文件已归档。阶段新增 121 次 Qwen 读取、935794 tokens、3547.93 秒执行器时间，6 次长度截断保留。各臂引用合并后的唯一个数为 208。联合臂相对锁定 PARSE 的 Diversity 平衡准确率 9/16→14/16，配对增量 0.3125 [0.0625, 0.5625]。OpenExempt EC、EV 相对 PARSE 的变化分别为 0.00490 和 −0.00318，两区间均跨零。ContractNLI 证据 F1 从 0.25569 到 0.36370，变化 0.10801 [0.05866, 0.16069]，同期共同教师臂也有同样分数。逐指标、实付成本和完整 B4 曲线见 `handoff/DEV_B4_native_effects_20261118.json`、`handoff/DEV_B4_physical_cost_audit_20261118.json` 与 `dev_curve_figures/B4`。

会话 2935 已终结。条件派生量诊断为两套程序提供完全相同的独立源审事实，所有权仍为未知。8 笔 Qwen 读数使用 47912 tokens，58 份绑定文件已归档。原生正候选的 4 条投影和旧程序的 4 条投影均返回对应的全部金额。逐例独立补全可以解释，跨查询的共享解释和固定单一解释均拒绝。首次在无字面错误通道下测得原生正候选的共享与独立补全分歧，但两程序均输出同一规则模式，尚无选择性更新收益。这一诊断保留 B4 原生评分和原技能库。见 `handoff/m2_oe_conditioned_value_current.json`。

B4 与条件诊断结算归档后，暂停缓存修复已应用。68 项测试和 2 个子测试通过。B5 未启动的旧绑定无物理记录，新绑定唯一变化为 `control_programs.py` 的暂停状态归档；进入技能库、固定 16 来源和 74 项任务、评分与模型配置保持一致。B5 正在会话 94033 做原生观察，入口 `handoff/formal_B5_observe_current.json`。TEST 原文和标签封存，Goal active。

## B5 共享所有权前向验证

B5 普通教师和锁定 PARSE 教师均接收相同的反馈。两套 B4 程序在要求转入和扣留同一财产的交叉查询上均返回全额。反馈要求解释在仅改金额时保持一致，并在所有权未决时保留不确定性。教师只接收这一行为摘要，不接收对应原文或原生标签。

B5 的 OpenExempt 新候选先和 M2 进入程序在固定 TRAIN 批上做原生配对。配对改善时才追加同源派生量比较。仅当字面事实已经通过、四项读数成对完整、独立补全支持候选、共享解释支持进入程序但排除候选时，该条件才单独否决更新。匹配回执记录原生、字面事实、独立补全、共享解释和单一解释的选择结果。B4 两套程序的 8 个已付请求已逐个精确重放，零新请求，复现两套程序均违反共享约束的模式。70 项定向测试及 2 个子测试通过。原绑定归档和重放回执分别见 `handoff/B5_M2_forward_preedit_archive_20261118.json` 与 `handoff/B5_M2_forward_replay_20261118.json`。

B5 观察会话 94033 正常终结。五臂各封存 16 个 TRAIN 来源及 74 项原生任务。44 个实际 Qwen 读数使用 307726 tokens，42 份源码逐一按哈希归档。用 B4 技能库测这批新来源时，两个 M1 臂均为 3/3，匹配对照均为 2/3。三例均实际走合成接口且逐关系全部通过源审。OpenExempt 保留原程序的两个臂相对各自对照 EC 平均 F1 增加 0.168198，四例均改善，EV 平均减少 0.002232。该程序差异来自 B4 字面事实选择。见 `handoff/B5_entering_native_comparison_20261118.json` 和 `handoff/B5_entering_M1_source_audit_20261118.json`。

唯一生成会话 31551 已从 `handoff/formal_B5_fit_current.json` 开始五臂拟合，当前实际进入普通教师 ContractNLI。绑定 59 份源码及上述共享比较。B5 拟合终结后归档并核验新提案选择，再接固定 B6。已结算的正式更新仍为 64/128，B5 观察累计 80/128。TEST 封存，Goal active。

## B5 回归检查及 B8 评分预检

B5 普通教师的 ContractNLI 提案在当批分类从 35/51 到 37/51，证据 F1 从 0.46405 到 0.37255。在此前 12 个 TRAIN 来源上，分类从 106/204 到 82/204，证据 F1 从 0.29301 到 0.21920。两批预测、原决策和实付记录均已核对。回归保护保留 B4 程序。见 `handoff/B5_CNI_training_regression_audit_20261118.json`。

最终评分完成后保存 ContractNLI 证据 F1 的适用题目范围和冻结哈希。后续复算直接用封存分数和该范围，并按每篇重采样合同的适用题数加权，使配对区间与原生按题平均指标一致。合成预检中，三个可评分题目的原生差是 1/3，旧等权合同算法给出 1/2，修订后复现 1/3。B1、B2、B4 的 DEV 效果回执原样复现，72 项定向测试及 2 个子测试通过。预检只读 TEST 身份元数据，160 个身份与连续账本请求的交集为零。真实 B8 评分仍待冻结。见 `handoff/B8_evidence_audit_preflight_20261118.json`。

B5 普通 OpenExempt 新提案在四个固定 TRAIN 来源上均低于 M2 进入程序。EC 平均 F1 从 0.189319 到 0.015625，EV 从 0.015625 到 0。两视图平均差为 −0.094659，未启动条件投影。提案将局部分流指令放入原生读者，三个完成的 EV 请求在原始模型输出中就只有一个资产，另一条长度截断。生产解码重放得到原封存输出。下一批可检验的修复是让局部组件条件只作用于带组件字段的投影，同时让原生分支按输入资产完成原生输出。待 B5 终态后再调整前向拟合，源审、两臂公平条件和原八批顺序沿用。见 `handoff/B5_OE_native_positive_gate_audit_20261118.json`。

会话 31551 已在教师请求边界退出，46 个 Qwen、6 个教师响应已结算，零在途。原 59 个源码哈希均一致。唯一生成会话 68552 已按原绑定恢复，并进入 PARSE 教师 Diversity。B5 完整更新和 B6 观察仍待，TEST 封存。公开代码和 B8 评分预检已核验至 `9f00e6ae4896519653fd2fd759c78483c1812032`。

## B5 五臂封存与 B6 执行

会话 68552 正常终结。五臂正式训练累计覆盖 80/128 个固定来源。B5 拟合结算 71 笔 Qwen 和 10 笔教师请求，消耗 567750 和 176913 tokens。原 59 份源码已按绑定逐一归档。普通教师和 M2 保留五库程序，PARSE 采纳 ContractNLI 更新，分类在当批 35/51→38/51、前四批 107/204→112/204，证据 F1 分别从 0.30642 到 0.38366、从 0.26330 到 0.29234。源审和有效记录见 `handoff/B5_training_terminal_audit_20261118.json` 与 `handoff/B5_CNI_PARSE_training_regression_audit_20261118.json`。M1 的 12 个时间顺序 TRAIN 来源上，现行与普通程序各 9/12，替代选择 8/12，现行合成路径中 4 条全关系忠实。见 `handoff/M1_incumbent_through_B5_20261118.json`。

B6 原定顺序的 16 个 TRAIN 来源和 74 个任务已绑定五个 B5 快照。当前唯一生成会话 19830，使用 `handoff/formal_B6_observe_current.json` 和 `handoff/run_state.json`，42 份观察源码保持一致。观察结算后归档并启动原五臂 B6 拟合。

B6 起普通 OpenExempt 教师在同一提案中提供原生读法、共享来源所有权规则以及局部派生组件计算。编译后两个读者共用同一段所有权规则，完整原生请求只使用原生读法和共有规则，带独立源审事实及合法组件字段的诊断才执行局部计算。PARSE 教师收到相同的 B5 失败摘要并继续输出锁定格式提案。两条路径均记录每视图返回与目标的资产数量，沿用原生得分与匹配选择。B5 原生 8 笔和 B4 条件投影 8 笔请求均精确重放，零新增模型请求，75 项定向测试及 2 个子测试通过。B6 真实效果等候新提案。见 `handoff/B6_OE_scoped_fit_preflight_v2_20261118.json`。TEST 封存，Goal active。

## B6 前向读数与最终初始库参照

B6 已完成的普通教师与仅 M1 两臂在三例 Diversity 上均为 3/3。M1 三次都走合成接口，所有局部关系经独立源审均受支持。此为 B5 库在下一批 TRAIN 的实际执行，随后的完整 B6 比较按原五臂结算。见 `handoff/B6_entering_M1_pair_audit_20261118.json`。

最终评估冻结时额外绑定原始 B0 共同库及源代码快照。静态库作为独立推理参照，在相同五库 160 个 TEST 来源上评分，正式五臂和训练轨迹仍按 B8 记录。已核对五臂的实际 B0 程序一致，且与已结算 B0 DEV 参照哈希相符。用 160 个合成身份验证全量预测封存后才评分，并验证参照独有请求与共享请求的去重记账。B4 真实成本旧回执原样复算，77 项定向测试及 2 个子测试通过。见 `handoff/B8_initial_reference_preflight_20261118.json`。真实 TEST 未打开，最终冻结和推理仍待 B8。

B5 与 B6 前向观察使用同一对 OpenExempt 程序，程序哈希已核验。在八个不同 TRAIN 来源上，B4 字面事实检查保留的程序相对普通臂，EC F1 平均增加 0.12190，批次分层配对区间 [0.06583, 0.17673]，七例升高、一例持平。EV 平均差 −0.01826 [−0.03604, −0.00112]，三例下降、五例持平。见 `handoff/B5_B6_OE_fixed_program_forward_20261118.json`。

B6 观察原会话 19830 在请求边界退出，39 个 Qwen 响应全部结算、零在途。会话 69078 已在原绑定恢复外部对照。原有 42 个文件逐哈希复核。结算后执行原定五臂拟合。见 `handoff/B6_observe_boundary_19830_20261118.json`。

会话 69078 已正常终结。五臂各完成 B6 的 16 个来源及 74 个任务，整个观察阶段结算 45 笔 Qwen 请求、387024 tokens，42 份源码按哈希归档。两组 M1 匹配比较均为 3/3 对 3/3。两组 M2 的 OpenExempt EC 和 EV 平均差为 0.07560 和 −0.03429，来源级原生回执 `handoff/B6_entering_native_comparison_20261118.json`。

唯一生成会话 29252 已开始 B6 五臂拟合，绑定 60 份源码、完整 B6 原生观察、实测 B5 反馈及固定的条件投影。原教师和冻结执行器保持一致。正式训练结算仍为 80/128，观察累计为 96/128。OpenExempt 新候选的资产数量和原生收益等待实际读数。TEST 封存，Goal active。

## B6 真实提案与 EV 资产绑定

B6 普通 OpenExempt 提案的八个原生请求均带共有所有权规则，且不带局部分流指令。四个 EC 响应保留参考资产数量，平均 F1 为 0.25992，相对 M2 进入程序提高 0.09405。四个 EV 均正常结束，但仍各只返回一个资产，平均 F1 为 0.01471，相对进入程序下降 0.10100。两视图平均效用相对普通进入程序增加 0.01717，相对 M2 进入程序下降 0.00348。因此共享投影未派发。见 `handoff/B6_scoped_fit_ordinary_candidate_audit_20261118.json`。

EV 修订按固定公开生成模板绑定案情中的每一项资产，输出槽区分省略、空申报与有值申报，保留原生评分映射。已用 B1–B6 的 24 条可见 TRAIN EV 原文恢复资产，与独立原生参考全部回译一致，其中一条参考省略了一项真实资产。隔离运行时复现普通与 PARSE 两条执行路径，未发新请求。只在 B6 封存后部署到 B7 及后续的匹配路径。见 `handoff/B7_EV_inventory_wire_preflight_20261119.json` 与 `handoff/B7_EV_isolated_runtime_preflight_20261119.json`。

最终 B8 DEV 跨库屏蔽增加了实际提案和推理请求的来源追踪。B1–B5 的四次联合臂程序更新均已按教师实付回执核对，B4 的 80 条联合臂 DEV 推理均已核对路由和物理请求，现有 B4 轨迹的跨库命中为零。B8 仍须在固定 DEV 实际运行屏蔽比较。见 `handoff/B8_transfer_provenance_preflight_v2_20261119.json`。TEST 封存。

B6 正常结算，共 49 笔 Qwen 和 10 笔教师请求，分别消耗 315972 和 176917 tokens，60 份运行源码已封存。普通臂接受 MAUD 与 OpenExempt，PARSE 接受 MAUD，M2 在 OpenExempt 保留进入程序。已复核前 96 个来源的五臂训练回执，并逐笔核对联合臂累计五次程序更新的教师来路。见 `handoff/B6_training_terminal_audit_20261119.json`。

截至 B6 的 15 个按时间顺序评估的 Diversity TRAIN 来源上，普通程序和现行 M1 均为 12/15，替代读器选择为 11/15。现行 M1 有 9 次合成读取，其中 7 次全部局部关系获源审支持。继续保留现行选择。见 `handoff/M1_incumbent_through_B6_20261118.json`。

已按预检部署共同 EV 资产槽，并保存 6 份变更前的原文件。B7 固定四个 EV 案情的公开资产槽数为 4、3、3、2，原有 PARSE 语法复核通过。44 份绑定文件、16 个原定来源和 74 项原生任务在唯一生成会话 6038 中观察。80 项定向测试和 2 个子测试通过。B8 DEV、最终 B0 参照、五臂冻结 TEST 及跨库屏蔽沿用相同 EV 读法。此前阶段保留其已封存读法。B7 真实收益尚待本批结算。见 `handoff/B7_bound_observe_preflight_20261119.json`。

B7 普通教师臂四个 EV 的原始请求、账本响应和原生解码逐笔复核，四例资产键均与参考完全一致，官方 EV F1 均值 0.11859。资产槽的得分效应仍待同源比较。见 `handoff/B7_EV_asset_inventory_actual_common_teacher_skill_learning_20261119.json`。公开分支已核验至 `0300bfec4cf7a4f3bca7067de3582d271286a151`。

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
