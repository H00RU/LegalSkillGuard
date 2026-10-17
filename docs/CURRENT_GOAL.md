# 当前Goal：恢复入口与证据边界

2026-10-17整理。此文件是操作索引，不替代实际Goal、进程和冻结工件。
近4000行历史游标已完整保存在
`docs/history/CURRENT_GOAL_before_compaction_20261017.md`；旧“下一步”不是当前指令。

## 完整目标不变

Goal active，目标尚未达成。保持ContractNLI法律任务、冻结律师参数及在线外部技能学习，
在不同合同上取得分类、原SPAN依据和联合正确性的稳定、实质净收益，胜过强空库、
等调用无技能核查和公平成熟经验学习方法。还须独立学习重复、机制消融、真实成本及
未调优正式TEST。不同难度批次裸分不要求机械单调，不预先承诺显著性或发表。
8案或32案已见训练拟合、单个固定库、输入/schema审计均不能替代这些要求。

原目标提及的 `legal_contractnli_answer_review_learning_20261015_run01` 不再运行。
其历史结果已归档；不要重启它或据此恢复9月多轮客户路由。

## 当前阶段：完整旧32终态，新32在线学习已后台启动

旧run `legal_contractnli_discriminative_evidence_full32_retention_20261017_run01`
18:25:37 CST完整完成，原worker2249247和保全worker2265836均已missing终态。
规范新调用计数`actual_new_native_teacher_calls:[48,0]`，另继承16个逐字相同实际回答，
共64不同raw，32原始已学合同配对。全部wire及原作者成员集合独立重数通过，0invalid/length。
**是固定库已学后保持，不是新案迁移、独立训练或四批学习曲线。**

| 条件（完整旧32） | 准确率% | 原SPAN Gold-NN F1% | 联合严格正确率% |
|---|---:|---:|---:|
| 技能 |85.294|66.734|56.618|
| 固定普通检索 |82.353|62.359|53.676|

净+2.941/+4.375/+2.941pp。分类39修正23损害，联合45修正29损害，真成员58增33失，
假引用25增39去。逐源F1 22胜4平6负；分类14/10/8、联合15/10/7。分类/联合区间跨0，
不能宣布稳定。第2原分组分类/联合为负；4组依据差值均正。分组不是学习曲线。
275漏证中224发生在分类正确时，context-only Gold仅采用13/118，取证尚未解决。
完整结果与全部变化在`runs/<旧run>/completion.json`，不可删坏结果或按分数选库。

终态保全已实际完成18:25:54：research目录
`full32_terminal_preservation_completion.json`，470项目文件/471成员，全部成员SHA核验，
两个不同文件系统同SHA`69a9db2ead1a1346029c97172209e88702fe5bc430884c07a529eaa48779d3a3`。
文件名`<旧run>-actual-terminal-recovery.tar.gz`。原317绑定未在运行/保全中修改。

新run **`legal_contractnli_member_learning_online_20261017_run01`**：

- 维护入口`python -m legal_skill_guard.learning.member_learning run configs/contractnli_member_learning_20261017.json`。
- 实际prepare及launch均已完成，**不得重复执行**。18:35:12 CST后台启动，worker
  **2326429**、start_ticks **423983002**；恢复时核真实`/proc`句柄，不只看状态文件。
- 实际launch/progress：`artifacts/research/member_learning_online_20261017/actual_launch.json`、
  `runs/<新run>/progress.json`；日志research同目录`stdout.log`。已冻结57文件。
- 19:08实际worker live，已完成38/176 native、1教师，处于B2 before（当前319 skills）。
  B1完整32 native/1教师已结束且双盘保全，负面结果见下；不要重复B1或改运行中的57文件。
- 新32源固定、空库起步、4批各8案，每批24真实before（空库/普通/技能），之后对全部seen
  8/16/24/32真实after，共176新native/4教师；不继承旧bank、raw或B1 aliases。
- 教师看所有seen原文/Gold及逐版本最新current-parent own，旧raw归档已教过；不按正确性选。
- 当前batch before是前向新案使用，after是拟合/保持，单独对同一旧案计算更新损害。
- 所有有效CRUD/NOOP/null直接发布；没有8案probe的“无准则终止”诊断guard。
- 协议`docs/MEMBER_LEARNING_ONLINE_PROTOCOL_20261017.md`；生成前已完整源码/Git双盘保全。
- 实际launch/progress为准，恢复时检查真实PID和ticks；观察超时不等于终止，绝不重复启动。

终态保全也已后台运行：worker **2328367**、start_ticks **423990359**，定义和实际launch
在新research同目录`terminal_preservation_definition.json`、`terminal_preservation_actual_launch.json`。
复用旧32已验证的保全程序，仅改3个run路径；成功/失败都等原worker真正终态后复制
全部闭合结果，实际完成须看`terminal_preservation_completion.json`，不凭计划说已备份。

## 当前可用方法和已完成证据

新维护实现：`legal_skill_guard/learning/member_contract.py`、`member_learning.py`。
旧8案/32案历史实现仍在research的`evidence_contract.py`、`run_study.py`，不作新主入口。
确定性源查询提供位置/访问角色，教师学习可选成员选择准则，冻结8B一次完成17命题的
原始choice/spans/reason。新编辑显式填准则文本或null；旧未动记录原样，null不交付。
无额外律师输出层、法律host判断、检索结果强制并入答案或效用准入。

真实bank SHA：`36d640efa852f94a4a374d37866a493435b186c7903e44498f5a72be875a4fb4`。
出版物：`runs/legal_contractnli_discriminative_evidence_skill_20261017_run03/publications/b5.json`。
8 UPDATE，16→16记录，8条准则覆盖9原命题；master2997/scope3225/准则投影427 tokens。

完整8已见TRAIN，32新native/1教师，0invalid/length，独立原作者及实际wire核算通过：

| 条件 | 准确率% | 原SPAN Gold-NN F1% | 联合严格正确率% |
|---|---:|---:|---:|
| 完整技能 |86.765|77.457|69.853|
| 同库同查询/角色、仅隐藏准则 |80.882|73.118|60.294|
| 无技能＋固定普通检索 |82.353|71.856|59.559|
| 强空库 |80.882|59.296|54.412|

同普通检索+4.412/+5.600/+10.294pp。分类净增6题全为source295净贡献，其余7源
合计0；不可说稳定。F1逐源5胜1平2负，联合5胜2平1负；NN严格联合31vs25，
不全是NM收益。相对隐藏准则，净真成员少1、假引用少12，主要是减少误引；context
Gold仅引2/15，且多数分类收益发生在准则scope外，不称语义隔离或完整取证已解决。
分类/F1对ordinary的8源条件区间跨0；这些区间不是独立学习稳定性或正式显著性。

核算/分析/全部损害原文在上述run的 `monitoring/`。原始8案不删、不手写case规则。
之前run02实际2native/教师1381因没有真正发布任何准则、消融两臂逐字相同而停止；
所有失败、出版物及成本保留。不要把它计作成功或抹去费用。

## 新32当前B1完整结果与下一决策（19:03完成，B2继续）

| B1同8原始合同 | 准确率% | Gold-NN依据F1% | 联合严格正确率% |
|---|---:|---:|---:|
| 学前强空库 |82.353|63.300|52.206|
| 学前固定M2，无技能 |83.088|54.348|52.206|
| 学后实际R1 |81.618|50.179|52.206|

首次1383教师51.969秒，63225输入/3093输出（reasoning2547）、0缓存/工具/重试。
实际CREATE1，nda-7第三方披露，8查询+真实选择准则，master408/scope512/投影140 tokens。
已独立核对实际teacher wire：完整8源/原Gold/136 own判断/全部成员对照，0未来/其他臂答案。
编辑schema没有“最多一次操作”限制；不按技能数量强制增长。

同案学后净少2分类，联合3修正3损害；真成员5增10失。h7的Gold16，C覆盖3，C∪P覆盖12，
却仍只引用5真成员（与学前相同），且分类2修正2损害。所有NN Gold183，C仅71，R1仅扩至80；
学后66 C成员+3额外成员+1池外=70 TP。普通检索已在学习前降低F1，不能把它算成技能学习退化。
说明此轮同时存在薄弱的固定检索覆盖/候选依赖及新技能使用不佳，不再声称缺Gold导致。

独立审计research同目录：`B1_before24_actual_teacher_and_equal_label20_original_audit.json`、
`B1_complete32_actual_source_member_and_all_harm_audit.json`。全部B1评分、6个分类损害公开回答保留。
B1不理想不直接重启：当前让同一真实R1进入B2不同合同，且B2教师会获得实际R1负面反馈。
若B2/B3在新案和同案更新中重复系统性损害，应停止整轮诊断，不硬拖/回滚/换案。
下一改动候选须优先检查固定M2前提是否持续伤害完整取证，而不是继续加提示字段。
移除这一前提尚未实施，也不能在查历史实际无工具分支前宣称“从未试过”。
mandatory source_queries>=1可能偏置选证型技能的表达，但这是未证实的机制假设，不据此强制多技能。
已失败的稠密/稀疏位图、强制检查、单题、support/refute不包装为新招；完整历史源示例交付
也已实现并负面（`legal_contractnli_contextual_experience_online_continuation_20261017_run03`），
旧研究记录“尚未实现fewshot”已过时，不能重新据它安排同样实验。

## 旧32完整漏证/损害审计（不是新32成绩）

`artifacts/research/member_learning_online_20261017/parent32_membership_and_all_damage_audit.json`
完整保留35个分类或联合损害问题的Gold、原文成员、两臂公开理由、分数、角色和raw引用。
该报告实际执行源码保存在Git `00b86e39f65d8708bc5a8dfb06bd333ab29b57f1`；之后只整理
该分析脚本的导入/重复IO/风格，未重跑模型或改报告。勿用当前源码SHA冒充历史执行SHA。

65个Gold>=3问题：技能分类60正确、联合仅2正确；漏160/246真成员。Gold=2问题漏90，
两类合计250/275漏证（90.9%）。这指向多成员完整返回的缺口，不是已证明唯一内部原因。
普通候选中的真成员相对ordinary新得7、丢24，不能只归因于低分额外邻居；例如603定义
已高分可见且准则要求带定义，却只返回操作条款。360独立重复支持也只返回其中一处。
完整系统提示本来已要求全部冗余支持，故不能把“再加一句收全依据”包装成新根因修复。
其余损害包含条件/例外、近题混用及公开理由与标签不一致；不称所有损害来自教师错规则，
不依据局部摘录改Gold，也不据此手写案件例外。新空库四批是当前实际验证，不修改运行库。

## 本次新32在线学习的数据与对照材料

`artifacts/research/discriminative_evidence_new_contracts_20261017/`：

- 当前bank逐SHA追溯6个真实发布至空库，祖先教学来源合计仅这32案。
- 排除bank32及普通检索器训练12案后，seed2026101702从剩余379个原作者TRAIN抽32案。
- `source_only_reserve32_inputs.json` 是原文/id/spans逐项相等的无Gold输入。
- 选择未使用标注值/得分，TRAIN容器为提取来源曾被解析，不声称从未解析Gold字节。
- 与44案交叉及内部496对都无原文/分词序列完全相同项；词5gram相似度仅源诊断，
  不是语义等价证明，未据此重选。正式DEV/TEST仍未打开。

此reserve不是新验证集或技能准入集，也不是已完成迁移结果。现已接入上述真实空库
四批学习；当前仍未完成，不把旧继承库或新run的启动称为独立重复成功。

公平监督量控制：`artifacts/research/same_label_ordinary_control_20261017/`。
仅CPU用原作者44案拟合同架构普通检索器，7.12秒，748原始配对，同超参数/0查询，
无新encoder/教师/律师权重更新。它未替换当前M2，未生成新合同回答或成绩。
未来推理请用 `ordinary_equal_source_label44.inference.manifest.json`（有规范state_sha256），
不是原始fit元数据；模型SHA已独立核对。它控制唯一来源/标签访问量，不代表算法
容量、算力或成熟方法已公平比较完成。这个44案模型只匹配当前“旧32案bank＋12案
背景工具”的静态迁移比较；新空库episode或后续在线更新的对照必须按其实际已揭示
来源重新拟合，不能只因总数相近就称监督量匹配。

新32自己的prefix控制已实际后台启动：worker **2344522**、ticks **424055060**。
程序research同目录`fit_revealed_prefix_controls.py`，定义/实际launch为
`prefix_control_definition.json`、`prefix_control_actual_launch.json`。18:49实际live等待B1发布。
只在真实b1/b2/b3/b4 publication存在且教学source IDs逐项相等后，CPU拟合12背景+8/16/24/32
已见源（20/28/36/44案），0native/教师，无query/新encoder/主M2替换。未来前缀从fit排除；
完整TRAIN容器会被解析，不声称未解析未来Gold字节。每个真实fit自动双盘校验备份。
首个20案fit已实际完成18:59:08，340原配对，实际204.421秒，非先验估计7秒。模型/参数/IDs/
未来24排除及双盘归档已独立核查。后续28/36/44仍等待真实发布，尚无control native成绩。
不是主方法或成熟方法胜利；与旧44案控制的具体来源不同，不可混用。
源定义和超参数不按分数选择；主worker终态且等不到下一发布时，它记录已完成前缀并退出。
CPU首fit曾64线程/32核超配；已核PID/ticks后短暂停同一worker，全部64线程限定30/31两核并
原PID恢复，没有fit重启/参数变化/主链路修改。暂停19:00其实已在首fit完成之后：初始“pickle
仍在写”的假设错误，准确时序单独保存在`prefix_control_actual_completed_fit_and_pause_timing_correction.json`，
原记录不删不改。后续核CPU只查这一个2344522句柄，不重复启动控制。

## 必须保持的执行边界

- 唯一工作树 `/media/sangfor/vdb/legal-skill-evolve`，hhy入口 `legal-skill-current`。
  `/home/yndx/hhy/legal-skill-evolve` 是另一个旧恢复树，不要混写。
- 8B服务 **2261314**、engine **2261698**；原权重磁盘文件已删、仅原服务RAM存活。
  **绝不重启/下载/切换模型**。同Qwen3-8B/BF16，seed45/T.6/p.95/k20/max8192，thinking开。
- 当前M2仅原12案，状态 `c0d59bbe7fa962b43f7ee3fe5adff98c6134c37419483263355be23fc881edb8`，
  pickle SHA `8453c3ed11bc02e4cc46b5b425399a2e2a3dbcc294a47d19b870cd91867a96c9`。
- 现有gpt-5.6-sol/high教师账本上限1400，当前预约序号1383；历史计数含已声明下界。
  不静默重置/加额，不增加付费API。新online已实际1教师，余3按原计划。
- 不恢复客户路由，不改法律任务，不加fallback/答案修补/效用准入/最好库回滚。
- 正式TEST不调优；全部不利结果和成本保留；不得把prepare、source编译或schema通过当效益。
- 5个既有untracked报告目录属于用户，不删不合并。

## 可恢复源码与结果

当前新主链路的完整源码/完整Git（无增量前置）、完整旧32实际结果、57冻结文件：
`legal-member-online-fresh32-prelaunch-full-source-and-Git-20261017.tar.gz`，3273项目/3275成员，
Git `449383e06691740d9f70190a8cc88e4b24c807e3`，
SHA `5cd674ec64467dcfa23babd441608952e9f35771b7866ced0189c126fabc32de`。
实际receipt：`artifacts/prelaunch_backups/legal_contractnli_member_learning_online_20261017_run01.json`。
两文件系统逐成员/整包SHA及完整Git bundle核验通过；不含尚未生成的新176答案。

2026-10-17完整源码/完整Git（无增量Git前置）＋完整8案raw＋新317绑定：
`legal-complete-eight-fourarm-and-full32-prelaunch-full-source-and-Git-20261017.tar.gz`，
SHA `2e47f06c5c0eee567ec023f1f534c9fc4c34bcee7298378b6424fe0e0d2fb10d`，3096项目文件。
同SHA已校验在 `/media/sangfor/vdb/legal-skill-backups` 和
`/home/yndx/hhy/legal-skill-rootdisk-backups` 两个文件系统。
这是同服务器备份，不是异地、权重、auth或整机快照；旧hhy下backup软链不是第二磁盘。
旧48调用终态归档已完成，见上方实际receipt；新176调用终态保全仍在等待，不能混称完成。
