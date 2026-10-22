# 当前Goal执行索引

2026-10-22 13:33 Asia/Shanghai。Goal仍active，完整论文目标未完成。
Run03已于12:09完整结束八批128来源/256任务，八次唯一最终发布齐全；
原等待PID于12:10自然exec为ACE128，主训练不得恢复、重启或误报为失联。
本索引覆盖先前运行状态；完整早期记录见
[历史记录](research/RUN03_EXECUTION_HISTORY_THROUGH_B7_C1_20261022.md)，
11:42八批首答检查点另保存了此前索引原文。旧“当前/下一步”不是本轮指令。

## 完整目标与边界

以单实例冻结Qwen3-8B，证明可演化法律技能在后续新案及最终隔离TEST上，
相对同权限/同推理预算的强空库、可信经验方法和自身B1库有可复核净收益。
优先完成OpenExempt EC/EV多批学习、真实行为修正、训练内反例回放与技能增删改。
不以机械单调裸分、技能数量增长、启动成功、单批胜空库或单次完整训练替代论文证据。
继续完成成熟对照、三次一致独立学习、必要消融、冻结矩阵/末库及隔离TEST。
师兄技能用于实证问题、机制、公平对照、损害与真实成本，不预设胜出或隐藏借鉴。
不新增付费服务/模型部署，不部署第二实例/32B，不引入fallback、隐藏求解器、
答案修复或无关扩展框架。不反复资格测试，不改评分、挑案例/旧好库或按结果调阈值。
保留全部失败、原始调用成本与双盘源码/数据/轨迹备份。用户补充见
[研究边界](research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md)。

## 当前真实运行与终态

- 项目：`/media/sangfor/vdb/legal-skill-evolve`；入口：`/home/yndx/hhy/legal-skill-current`。
- 已完成主Run：`legal_openexempt_closed_feedback_public_assets128_20261021_run03`。
  unit：`legal-openexempt-closed-feedback-public-assets128-20261021-run03.service`；
  MainPID=0、inactive/dead、Result=success、ExecMainStatus=0；
  completion状态`completed_bounded_mechanism_study`，没有failure，八批均完整。
  这是自然完成，不是训练服务丢失；旧Run02也不得恢复。
- 原模型unit：`legal-qwen3-8b.service`，PID3613253/start446037091，engine3613750。
  Qwen3-8B bf16 revision `b968826d9c46dd6066d109eabc6255188de91218`。
  12:29单A40为25009/49140MiB、98%，未替换模型或增加实例。
- 正在训练ACE：`legal_openexempt_ace_public_assets128_20261021_run01`。
  unit：`legal-openexempt-main128-run03-to-ace128-20261021-run02.service`；
  原等待PID1738522/start455481667，12:10:34.941356 CST已exec
  `experiments.openexempt_ace_online run`，不是另起重复任务。
  13:27完整B1首答已落盘：16来源/32任务/96逻辑记录，64原始生成/HTTP全stop、0解析错。
  原生ACE冷启动EC59.53125/EV55.29514%，共用直接空库63.44990/66.35417%；
  初始0技能，差异是原生提示包装效应，不是技能学习优劣，不据此提前宣称胜ACE。
  32个共用空库请求、原生回答内容和评分与主Run逐一精确相同。
  13:33实际68生成/5教师，正在181的EV训练重答；B1尚未最终发布，仍无成熟ACE成绩。
  初始化仅原生七个空标题，0法律先验/0数值程序，无旧库或主训练记忆导入。
  ACE原生Generator/Reflector/ADD curator，最多3轮TRAIN反思；不是作者默认原样复现，
  也不是总训练计算量相等。共享执行器、输入、EC/EV契约与生成上限，消耗成本另报。
  目前只运行ACE45；另外六配置未排队，不擅自加多任务调度器抢GPU。
- canonical锁：`artifacts/openexempt_training.lock`。
- 当前只读观察session **67586**，13:28:03启动，目标ACE B1唯一最终发布及32条
  实际TRAIN轨迹齐全；期限19:28:03仅结束观察，不结束训练。
  旧15458于13:27:16看到完整首答正常退出0，CPU31275已完成独立原始评分/投递审计，
  包装cell7463也已正常完成，不得再轮询。目标/终态制品优先于进程缺失判断；
  仍须核PID/start ticks/argv，不能仅凭索引、锁、progress或观察超时判断停训。
  旧11058/34994/46189/61360/94323/85265/88537均已完成，不再轮询。
- 13:30方向复核完成；下一小时14:30 CST。原主PID不再存活是正确终态，
  不复用仍要求main存活的旧小时/保全程序。

## 冻结协议与保真

学习/执行代码仍`6896246`，后续只改证据与文档，不改本Run算法。
主配置SHA `8c858d27892f278ee9cdd6c251486ce2080637aa5f01c51d165ecdab5fe2122e`；
主frozen371清单SHA `2cc50e6cfe05fb42c230aba570eb43e9fcd41c3287011f77de8291fd89418825`。
ACE配置SHA `b9d21b0772cee5ab297d61367a1232fa96767f3ead5e7ede9a3bfa8074776c76`，
12:10:34首次本轮性能前冻结382文件/50packages。终态审计核主371、ACE382和环境均原样。
共享教师上限在主终态后按已授权接续1797→3349，不删除历史预约。

128固定TRAIN来源181–308，8批各16来源，每源独立EC/EV，共256任务。
custom profile为2–4资产、五州、公开可用法域/start2，不是官方Advanced或OOD。
v14 `direct_statutory_claims`、`legal_scope`、`carry_partial_and_refine`；
EC/EV独立直接回答，无EC答案向EV传递，公开资产/法条引用对所有角色相同。
主库上限4096完整序列化tokens；每批至多2次教师提案，不是一条技能操作。
允许CREATE/UPDATE/DELETE/MERGE/NOOP，不强制增长或收录。
教师gpt-5.6-sol/high，给全当前16来源与最多16旧来源、最多64任务标签；
B1无历史、仅32任务。给真实父观察和有界失败反馈，推理尾1024字符仅作未验证证据。
本批全部首答先保存，再评分/提供标签；无验证集、未来标签或TEST反馈。
全部已见TRAIN重放、当前/旧组任务/法域连通作用域与整库门槛保持不变。
不是逐案零回退，但有合并净益仍因分组退化拒收的保守性；不能热改门槛美化曲线。
固定执行器32768上下文/8192输出，thinking开，temp0.6/topP0.95/topK20/seed45；
vLLM0.10.2/xgrammar1.23/serverseed42/maxseq1/prefixcache关/KV5368709120。
三个空库名称为精确同请求别名，不是三独立基线或额外样本。

## 完整八批新案首答与实际发布

单位为F1百分比；这些都是看到本批答案之前的首答，不是批后回放或TEST。
批后库仅供后续新案使用，不反向替换本批分数。

| 批次 | 空库EC / EV | 在线EC / EV | 对自身B1 EC / EV (pp) | 批后条数 / tokens |
|---|---:|---:|---:|---:|
| B1 | 63.45 / 66.35 | 63.45 / 66.35 | 尚未定义 | 5 / 1591 |
| B2 | 68.71 / 64.51 | 83.68 / 74.45 | 0 / 0，按设计相同 | 6 / 1945 |
| B3 | 64.70 / 60.79 | 91.42 / 82.42 | +0.89 / +6.72 | 6 / 1945，拒收后NOOP |
| B4 | 54.95 / 57.17 | 83.85 / 79.84 | −0.67 / +5.00 | 6 / 2179，改AZ EV |
| B5 | 55.97 / 65.31 | 86.77 / 80.83 | +1.69 / +5.43 | 6 / 2182，改IL EV |
| B6 | 56.31 / 67.72 | 84.60 / 83.44 | +2.01 / +18.48 | 6 / 2202，改FED/PA EV |
| B7 | 58.13 / 61.56 | 78.55 / 80.76 | 0 / +16.24 | 6 / 2223，改IL EC |
| B8 | 59.12 / 59.96 | 83.90 / 85.21 | +2.07 / +13.89 | 7 / 2486，增WI EV |

包含按设计相同B2的112新来源，对自身B1 EC+0.85565/EV+9.39396pp；
B3–B8全部96来源为EC+0.99826/EV+10.95961pp。单学习器TRAIN，非独立重复/统计显著。
不同批次案件不同，不把裸分变化当同案遗忘或宣称机械单调。
**B1占位陷阱**：原completion全128来源的frozen_after_B1汇总包含B1空库占位，
不是学得B1库在B1案件上的预测；原始文件不改，报告持续进化只用上述112/96来源。
最终评测的真实B1控制仍是首次唯一5条/1591tokens，未挑更好的早期库。

机器曲线`Run03_learning_curve_complete_prequential_batches_20261021.json`已更新为
8首答/8最终发布，所有首答点不变；不可变终态快照为
`Run03_learning_curve_complete_first8_final8_publications_20261022.json`。
上述均在`artifacts/research/openexempt_legal_scope_20261020/`。
八批46点图位于`artifacts/research/learning_curves_20261022/Run03_B1_B8_prequential/`；
11:32输出的“B8 update pending”是当时快照，不代表当前未结束。不覆盖旧图或虚构CI。

## 真实技能收益与尚存缺口

ACE B1完整首答报告：
`ACE128_B1_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261022.json`。
原生角色空playbook当前低于直接空库，32任务4好14坏14平；不是解析/截断或空库
请求变化，不热改作者角色或据初始空库判断最终效果。须继续实际教师、curator及后续新案。
首批固定成本64生成/64 HTTP、421456输入/158202输出，包含角色包装和直接空库，
不是已进行中的训练重答成本。181 EC的三次实际教师请求均核到完整正确标签字面值，
全新gpt-5.6-sol/high、无工具/缓存；三响应66467输入/2114输出，非当前教师总量。
小时证据`hourly1330_ACE128_complete_B1_first96_actual_teacher3_labels_and_original_service_bindings_20261022.json`。
GPU在13:29学生重答为96%，13:31教师阶段为0%；模型/ACE原句柄都在，不能把正常
教师阶段GPU闲置误判成模型服务退出。历史350预约前缀保持，369预约/3349为当时账本快照。

B7最终`a232fc0b795b84155526b411f4c19a5143441ac47ef8ff25e1eaa3781f032e0a`。
C1广泛改写有实际损害，已全部拒收；C2仅改IL EC一句，EV全保留。
B8全部32个父B6请求均精确匹配本批已观测原始输入/输出，无新推理；
仅293/302两IL EC受新句影响，一平一坏，折全批−0.69444pp。
旧OR改动贡献+2.76538pp，合计+2.07093pp；不能将总收益归于最新IL修改，n=2也不证明总体有害。

B8最终bank `3387b5b450f4b9107c9738562fa224915bb4405ff329ca8f113fc05d0e9c76e7`，
12:09:47.540779 CST唯一发布；只CREATE一条WI EV技能，原六记录逐字保持、所有EC不变。
C1完整128来源/256任务/768位原始v14/消息/评分/门槛审计已完成。
当前16案EV85.20585→87.01141%、旧112案89.56072→89.62591%；
128来源11好8坏109平（全EC不变）。这些是TRAIN回放，不替换B8首答85.20585%。
原10处WI车辆4000错误全部仍有相应声明且精确修到金标，不是删引用消错；
同时出现9个新非WI金额错误，缺失声称80→83，错金额72→67，额外法条17→13。
不能说所有金额已修好，B8新技能的后续泛化还待独立测试。
TRAIN283公司用途与一般个人用途条款/金标的字面张力仍未专家裁定，不改案/标签/评分。

## 实际成本、双盘保全与下一步

完整主Run：1158原始生成/1158 HTTP，全stop；7655443输入/3232344输出tokens。
15次新鲜教师3232522输入/51361输出，reason35912已包含输出；
响应耗时1132.442秒不是GPU小时。包含全部失败候选，不含ACE/静态/早期研究/部署。
终态成本报告：`Run03_complete_B1_B8_actual_terminal1158_15_cost_20261022.json`。

自动actual-terminal双盘各10014成员已独立复核所有成员字节相同，设备64528/64517；
它们只包含本Run轨迹，不能假称内部含371源码。源码另有已核原source档和11:42联合档。
vdb档SHA `27b265caf217e7310fe6ecdbfdc862a58781e402192d695048f4ec50d8377947`；
root档SHA `ba80ecd9f8fe28b05f95a7ea052dd5688ce8af5dead8ae7336bc9174619a29ae`。
终态综合审计：
`Run03_actual_terminal8_publications1158_15_dual_runtime_archive_WI_skill_repairs_and_B1_placeholder_audit_20261022.json`。
12:42联合双盘检查点已完成，14469成员逐字核验，包括全部当前跟踪文件、主371/
ACE382/static117绑定源码、主训练完整轨迹/1158原始生成/15教师及八次发布、
新终态审计/曲线/成本、本文档/证据账本与ACE不可变初始化和接续元数据。
不纳入在写ACE progress或部分性能，不覆盖旧档。
收据：
`Run03_actual_terminal8_complete_source1158_cost_WI_repairs_B1_boundary_and_ACE_start_joint_preservation_20261022.json`。
联合vdb档SHA `80949b16434a10f9dbb6fd947d6a83d473166b45a41909670c7ab9fb257325f0`；
root档SHA `1f5c1afa2fb07d85217e655a2d3d7bb2530f1bd3e6903268a05b5992ff99817e`。

下一步持续观察ACE全部八批，不据空B1判断成熟方法优劣，不另起重复进程。
[最终分析计划](research/OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md)保持：
主/ACE各三次一致独立学习seed45/145/245，静态7条/2411tokens仍待性能，
whole-bank/first-commit必要消融必须实际独立学习，不能手删末库冒充。
所有矩阵、配置和末库须首次TEST预测前冻结；128来源配对cluster bootstrap20000次，
八主/四次要比较；不将EC/EV或三学习器复制为更多独立来源。
SkillCommit近邻须引用，无原实现/已授权原编码服务，不冒称复现或SOTA。
封存IID128 TEST未读语义/预测/标签/结果，字节hash
`6a5f72559a021d425d5b6ee41ba19f1a8e10d7da1ac11e0725d469a281c5164d`。
正式Results仍PENDING，目标未完成；当前不再把旧B8待完成状态当后续工作。
