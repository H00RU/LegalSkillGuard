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

## 当前阶段：完整旧32终态，准备新32在线学习

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
- 实际prepare已完成，57冻结文件，0生成/教师；新run尚未启动，不能重复prepare或宣称训练完成。
- 新32源固定、空库起步、4批各8案，每批24真实before（空库/普通/技能），之后对全部seen
  8/16/24/32真实after，共176新native/4教师；不继承旧bank、raw或B1 aliases。
- 教师看所有seen原文/Gold及逐版本最新current-parent own，旧raw归档已教过；不按正确性选。
- 当前batch before是前向新案使用，after是拟合/保持，单独对同一旧案计算更新损害。
- 所有有效CRUD/NOOP/null直接发布；没有8案probe的“无准则终止”诊断guard。
- 协议`docs/MEMBER_LEARNING_ONLINE_PROTOCOL_20261017.md`；生成前须完整源码/Git双盘保全。
- 实际launch/progress为准，恢复时检查真实PID和ticks；观察超时不等于终止，绝不重复启动。

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

## 下一阶段已准备的材料（还没启动新合同训练）

`artifacts/research/discriminative_evidence_new_contracts_20261017/`：

- 当前bank逐SHA追溯6个真实发布至空库，祖先教学来源合计仅这32案。
- 排除bank32及普通检索器训练12案后，seed2026101702从剩余379个原作者TRAIN抽32案。
- `source_only_reserve32_inputs.json` 是原文/id/spans逐项相等的无Gold输入。
- 选择未使用标注值/得分，TRAIN容器为提取来源曾被解析，不声称从未解析Gold字节。
- 与44案交叉及内部496对都无原文/分词序列完全相同项；词5gram相似度仅源诊断，
  不是语义等价证明，未据此重选。正式DEV/TEST仍未打开。

此reserve不是新验证集或技能准入集，也不是已完成迁移结果。后续应检验新合同上的
实际在线学习及独立重复；不能永久停在旧案复测或把当前继承库称为从空库独立训练。

公平监督量控制：`artifacts/research/same_label_ordinary_control_20261017/`。
仅CPU用原作者44案拟合同架构普通检索器，7.12秒，748原始配对，同超参数/0查询，
无新encoder/教师/律师权重更新。它未替换当前M2，未生成新合同回答或成绩。
未来推理请用 `ordinary_equal_source_label44.inference.manifest.json`（有规范state_sha256），
不是原始fit元数据；模型SHA已独立核对。它控制唯一来源/标签访问量，不代表算法
容量、算力或成熟方法已公平比较完成。这个44案模型只匹配当前“旧32案bank＋12案
背景工具”的静态迁移比较；新空库episode或后续在线更新的对照必须按其实际已揭示
来源重新拟合，不能只因总数相近就称监督量匹配。

## 必须保持的执行边界

- 唯一工作树 `/media/sangfor/vdb/legal-skill-evolve`，hhy入口 `legal-skill-current`。
  `/home/yndx/hhy/legal-skill-evolve` 是另一个旧恢复树，不要混写。
- 8B服务 **2261314**、engine **2261698**；原权重磁盘文件已删、仅原服务RAM存活。
  **绝不重启/下载/切换模型**。同Qwen3-8B/BF16，seed45/T.6/p.95/k20/max8192，thinking开。
- 当前M2仅原12案，状态 `c0d59bbe7fa962b43f7ee3fe5adff98c6134c37419483263355be23fc881edb8`，
  pickle SHA `8453c3ed11bc02e4cc46b5b425399a2e2a3dbcc294a47d19b870cd91867a96c9`。
- 现有gpt-5.6-sol/high教师账本上限1400，当前预约序号1382；历史计数含已声明下界。
  不静默重置/加额，不增加付费API。当前保持检查0教师。
- 不恢复客户路由，不改法律任务，不加fallback/答案修补/效用准入/最好库回滚。
- 正式TEST不调优；全部不利结果和成本保留；不得把prepare、source编译或schema通过当效益。
- 5个既有untracked报告目录属于用户，不删不合并。

## 可恢复源码与结果

2026-10-17完整源码/完整Git（无增量Git前置）＋完整8案raw＋新317绑定：
`legal-complete-eight-fourarm-and-full32-prelaunch-full-source-and-Git-20261017.tar.gz`，
SHA `2e47f06c5c0eee567ec023f1f534c9fc4c34bcee7298378b6424fe0e0d2fb10d`，3096项目文件。
同SHA已校验在 `/media/sangfor/vdb/legal-skill-backups` 和
`/home/yndx/hhy/legal-skill-rootdisk-backups` 两个文件系统。
这是同服务器备份，不是异地、权重、auth或整机快照；旧hhy下backup软链不是第二磁盘。
当前48调用终态会自动生成额外结果归档，必须读取其实际完成receipt，不凭计划说已保全。
