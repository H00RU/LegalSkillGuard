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

## 当前真正运行的任务

- Run ID：`legal_contractnli_discriminative_evidence_full32_retention_20261017_run01`。
- worker **2249247**，start_ticks **423671093**；恢复时须核 `/proc` 实际句柄与ticks。
- 配置：`artifacts/research/discriminative_evidence_skill_20261017/full32_retention_config.json`。
- 入口：同目录 `continue_full32.py`。**prepare和launch均已执行，不要重复。**
- 启动：2026-10-17 17:43:13 CST；18:10:18快照为31/48新native、0教师，当前364 skills。
- 实际进度：`runs/<Run ID>/progress.json`；日志：research同目录 `full32_retention.stdout.log`。
- 317初始冻结绑定及全部48先验输入在首答前保全；不要修改绑定文件。

本任务固定同一实际16记录/8准则bank，不训练教师，不改查询、提示、模型或评分。
完整8案已完成的16个skills/ordinary回答先逐字核对输入后显式继承；其余全部24案
各两臂48新调用。最终64个不同真实raw，32份原始合同配对比较。继承16不算新调用。
**全部是已学后保持，不是新案迁移、独立在线训练或四批学习曲线。**

完成记录：`runs/<Run ID>/completion.json`，规范计数键是
`actual_new_native_teacher_calls: [48, 0]`，不是`completed_native_calls`。
入口自动核对64实际wire/原作者TRAIN并重数SPAN集合，报告逐组、错误和source区间。
未完整时不看部分正确率，不重启B1，不按暂跌选择库或补答案。

## 终态保全也已后台运行

保全worker **2265836**，start_ticks **423737941**，等待上面的原worker真正退出。
定义/启动记录位于research同目录：
`full32_terminal_preservation_definition.json`、`full32_terminal_preservation_actual_launch.json`。
完成后看 `full32_terminal_preservation_completion.json`，实际成功/失败均原样保留。
它将冻结源码/输入/全部实际输出逐成员校验并复制不同文件系统，不调用任何模型。
**主worker终态后，也须等保全结束再改317个绑定文件。**
观察超时不是进程终止；仍live则检查同一句柄，不因没新输出重复启动。

## 当前可用方法和已完成证据

方法实现：research目录的 `evidence_contract.py` 与 `run_study.py`。
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
