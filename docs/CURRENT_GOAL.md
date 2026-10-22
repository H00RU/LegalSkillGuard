# 当前Goal执行索引

2026-10-22 Asia/Shanghai，状态依据11:24完整B8首答、11:26真实教师及11:34小时核验。
Goal仍active，完整论文目标未完成。八批128来源首次作答齐全，仅七次最终发布；
原Run03正在B8候选1学习回放，不等于完整八批学习已完成。
历史1237行已完整迁入[历史记录](research/RUN03_EXECUTION_HISTORY_THROUGH_B7_C1_20261022.md)，
其中的旧“当前/下一步”不是本轮指令。先核真实PID/start ticks/argv，再读progress；
索引、锁或观察期限都不单独证明训练存活或终止。

## 完整目标与边界

以单实例冻结Qwen3-8B，证明可演化法律技能在后续新案及最终隔离TEST上，
相对同权限/同推理预算的强空库、可信经验方法和自身B1库有可复核净收益。
优先完成OpenExempt EC/EV多批学习、真实行为修正、训练内反例回放与技能增删改。
数据/任务服务于论文，不因已投入时间锁死，也不遇单个负点就换名重启。
不以机械单调裸分、技能数量增长、启动成功或单批胜空库替代完整证据。
必须继续成熟对照、三次独立一致学习、必要消融、冻结矩阵/末库及隔离TEST。
当完整主曲线和成熟对照支持优势即可写正文，重复/统计可同步；未出的数字标待补。
师兄技能用于实证问题、真实机制、公平对照和成本，不用于预设胜出或隐藏借鉴。

不新增付费服务或模型部署，不部署第二实例/32B，不引入fallback、隐藏求解器、
答案修复或无关扩展框架。不反复资格测试，不改评分、挑案例/旧好库或按结果调阈值。
保留全部失败、原始调用成本与双盘源码/数据/轨迹备份。用户补充仍见
[研究边界](research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md)。

## 唯一当前运行与真实句柄

- 项目：`/media/sangfor/vdb/legal-skill-evolve`；入口：`/home/yndx/hhy/legal-skill-current`。
- 主Run：`legal_openexempt_closed_feedback_public_assets128_20261021_run03`。
  unit：`legal-openexempt-closed-feedback-public-assets128-20261021-run03.service`；
  PID1721740/start455413980，10/21 09:53:42 CST启动。未重启；旧Run02不得恢复。
- 模型unit：`legal-qwen3-8b.service`，PID3613253/start446037091，engine3613750。
  Qwen3-8B bf16，revision `b968826d9c46dd6066d109eabc6255188de91218`。
  09:30单A40为25009/49140MiB、97%，无模型替换或第二实例。
- 原ACE等待器：`legal-openexempt-main128-run03-to-ace128-20261021-run02.service`，
  PID1738522/start455481667，10/21 10:04:59启动。只排ACE45，尚未训练。
  等完整主8批/128来源/256任务及最终双盘备份后，在同等待PID/锁内exec ACE。
  另外六配置未排队，不擅自另起调度器或与主训练抢GPU。
  若原main句柄自然消失，先核`completion.json`完整八批及`publications/b8.json`，
  再查该PID是否已exec为ACE及队列完成/失败制品；不能把正常终态当作故障重启。
  主完成后不盲跑仍要求main存活的旧小时审计或保全程序，须以真实终态核验替代。
- canonical锁：`artifacts/openexempt_training.lock`。

当前只读观察为原生session **11058**：目标是B8候选1完整决定或B8唯一最终发布；
11:26:24启动，期限14:26:24只结束观察，不结束训练。目标制品优先于main句柄
检查，覆盖NOOP与主训练自然完成。旧46189于11:24:24看到完整首答正常退出0，
包装7409、CPU61360/94323均正常完成，不得再轮询；当前无functions包装运行。
下一小时方向核对 **12:30 CST**，不要将观察超时当成重启理由。

## 冻结协议与原始绑定

学习/执行代码仍`6896246`。后续仅文档/离线图脚本提交，不等于改算法。
配置：`configs/openexempt_closed_feedback_public_assets128_20261021_run03.json`，
SHA `8c858d27892f278ee9cdd6c251486ce2080637aa5f01c51d165ecdab5fe2122e`。
frozen371清单SHA `2cc50e6cfe05fb42c230aba570eb43e9fcd41c3287011f77de8291fd89418825`。
11:34 main371/static117/ACE等待381文件及50packages均原样保持。

128固定TRAIN来源181–308，8批各16来源、每源独立EC/EV，共256任务。
custom profile为2–4资产、五州、公开可用法域/start2，不是官方Advanced或OOD。
v14 `direct_statutory_claims`、`legal_scope`、`carry_partial_and_refine`；
EC/EV独立直接回答，无EC答案向EV传递。公开资产/法条引用对所有角色相同。
库上限4096完整序列化tokens；每批至多2次教师提案，不是只允许一次技能操作。
允许CREATE/UPDATE/DELETE/MERGE/NOOP；不强制增长或收录。
教师gpt-5.6-sol/high，提供全部当前16来源与最多16旧来源、最多64任务标签，
B1无历史来源、仅32任务；并提供真实父观察和有界失败反馈。
模型发出的推理只供未验证证据，尾1024字符有界，全原始记录保留。

所有本批首答先保存，再评分和提供标签；无验证集，无未来标签或TEST反馈。
候选在全部已见TRAIN上比较父库，实际任务/法域连通作用域及整库需当前/旧组
原生与完整输出F1不退、错误计数不增，且当前至少一项改善。不是逐案零损失。
它确有保守性；旧审计有6个净益但分组退化的拒收分量，也有大量真实有害提案。
本Run不热改门槛，不从已见成绩倒推容忍阈值，不把回放当独立泛化证据。

固定执行器32768上下文/8192输出、thinking开、temp0.6/topP0.95/topK20/seed45；
vLLM0.10.2/xgrammar1.23/serverseed42/maxseq1/prefixcache关/KV5368709120。
不得因候选正常拒收、NOOP、历史NCCL警告或观察结束而重启。

## 已完成的新案成绩，不是训练回放

每批16来源；B1控制从首次唯一最终B1库开始固定，不能挑最佳早期库。
三个空库名称为精确同请求别名，不是三独立基线或额外样本。

| 首答批次 | 在线EC / EV F1 (%) | 相对自身B1 EC / EV (pp) | 批后实际条数 / tokens |
|---|---:|---:|---:|
| B1 | 63.45 / 66.35 | 尚未定义 | 5 / 1591 |
| B2 | 83.68 / 74.45 | 0 / 0，按设计相同 | 6 / 1945 |
| B3 | 91.42 / 82.42 | +0.89 / +6.72 | 6 / 1945，拒收后NOOP |
| B4 | 83.85 / 79.84 | −0.67 / +5.00 | 6 / 2179，改AZ EV |
| B5 | 86.77 / 80.83 | +1.69 / +5.43 | 6 / 2182，改IL EV |
| B6 | 84.60 / 83.44 | +2.01 / +18.48 | 6 / 2202，改FED/PA EV |
| B7 | 78.55 / 80.76 | 0 / +16.24 | 6 / 2223，改IL EC |
| B8 | 83.90 / 85.21 | +2.07 / +13.89 | 待学习完成，入批6 / 2223 |

B7强空库EC58.125/EV61.5625%；在线EC78.54663/EV80.75521%，来源9好2坏5平。
本批所有EC请求与自身B1精确相同，因为此前唯一后B1 EC变化在Oregon，本批无Oregon。
不能由EC持平推断模型不可能再学EC。B3–B8的96新来源相对B1 EC+0.99826/
EV+10.95961pp，含按设计相同B2的112来源为+0.85565/+9.39396pp；均是单学习器TRAIN。
不同批次案件不同，裸分下降不能直接当同案遗忘，也不能称单调改善或统计显著。

机器曲线：`artifacts/research/openexempt_legal_scope_20261020/Run03_learning_curve_complete_prequential_batches_20261021.json`。
新固定快照：同目录`Run03_learning_curve_complete_first8_snapshot_20261022.json`。
八批PDF/PNG在`artifacts/research/learning_curves_20261022/Run03_B1_B8_prequential/`；
旧40点逐点不动，新增6点共46点，600dpi PNG及矢量PDF/SVG已渲染检查，所有源/
输出SHA与6000x2700尺寸核同。不平滑、不画虚构CI，不把回放或TEST放进曲线。

## B7学习终态与正在验证的迁移

09:32:03.930275 CST唯一B7最终bank：
`a232fc0b795b84155526b411f4c19a5143441ac47ef8ff25e1eaa3781f032e0a`，6条/2223tokens。
C1全部拒收，C2只接收`EC:ILLINOIS`。实际净UPDATE1，无CREATE/DELETE/MERGE。
只在原IL EC avoid_when末尾增加不动产排除一句，所有EV及其他字段逐字保持。

C1完整112来源/224任务/672位审计：当前EC/EV78.55/80.76→71.25/75.03%，
旧96案85.95/91.03→80.20/85.79%；真实损害，不是仅因准入严格。52生成全stop/无格式错。
IL通用(b)漏引EC15→46、EV13→40。283住宅金额30000→15000虽修对一处，
却损坏其他答案。拒收6139库没有进入实际运行。

C2完整672位已复算，52新生成全stop/无格式错。实际EC当前16案78.54663→
82.71329%、旧96案85.95445→86.93824%；EV保持父结果。112来源6好1坏105平，
旧190 EC1→0.91667仍获接收，说明不是逐案零回退。上述是TRAIN重放，不改首答曲线。
全C2提案的EV当前80.75521→76.14211%、未评分/负目标声称1→6，实际已剔除；
即便旧EV均分稍升，也不是一个已证明净益的被保守拒收修改。

当前性能证据均在`artifacts/research/openexempt_legal_scope_20261020/`：

- `Run03_B7_candidate2_complete224_all672_native_wire_gate_and_claim_failure_diagnostics_20261022.json`。
- `Run03_B7_unique_final_EC_boundary_gain_EV_harm_rejected_and_B8_actual_delivery_20261022.json`。
- `Run03_B7_teacher2_actual64_unchanged_parent_real_C1_feedback_two_boundary_sentences_C2_delivery_20261022.json`。

B8原进程10:30已到来源300；首源293为IL，09:43全部EC/EV角色10输入/10回答
均核同，skills收到真实a232，六原始生成全stop/零解析错，EV未泄漏被拒修改。
不是完整B8结果，未读部分B8评分或标签。
上述是当时的健康前缀；完整B8首答已在11:24完成，不能继续等待已完成的46189。
10:30快照已核80计划输入/79完成逻辑回答、40原始引用全部stop、零解析错，
未读部分B8评分或标签；原三句柄及绑定保持，单A40原引擎25009/49140MiB、98%。
365预约/1797、14教师，旧350未动，ACE未开始。本Goal轮为原46189/7403核实
等待，不是新性能提升；7403正常到达小时边界，未停止原46189或main。
证据：`hourly1030_Run03_B8_actual_B7_final_control_delivery_health_and_original_bindings_20261022.json`。
CPU85265正常退出0，不再轮询。B1教师无旧来源，仅32任务；64为后续最大任务数，
本文档措辞已澄清，未改变任何实际训练设置或数据。
10:32:02上述固定80输入/79回答/40健康原始引用、当前索引及前3604成员检查点
收据共204成员已双盘逐字节核验保全；前后371/381/50packages及原三句柄不变。
收据：`hourly1030_B8_final_bank79_healthy_answers_preservation_20261022.json`。

## B8完整首答与当前最后一批学习

293–308全部16来源/32任务/160逻辑记录原始v14解码、原生/完整评分、父库/
控制及请求预算均复核一致。84原始生成/HTTP全stop、零格式错，552300input/
232803output。强空库EC59.11954/EV59.96032%，B1为81.83036/71.31944%，
在线83.90129/85.20585%。对B1 EC+2.07093/EV+13.88641pp，来源10好3坏3平；
不是正式TEST或独立重复。报告`Run03_B8_complete160_newcase_final_B7_vs_ownB1_native_wire_cost_and_scope_20261022.json`。

不得把总EC增益归于最新IL修改：全部32个B6父库请求均找到本批已观测的精确
同输入/输出，按输入匹配而非成绩选角色，没有额外生成。仅293/302两IL EC
实际暴露新句，前者1→1、后者1→0.88889，最新改动全批EC贡献−0.69444pp；
早期OR变化贡献+2.76538pp。n=2不能推断总体有害或证明已迁移成功。此为固定
原生请求复用诊断，不是新增独立B6评测臂。报告
`Run03_B8_all32_observed_exact_wire_parent_B6_coverage_and_latest_B7_EC_vs_accumulated_skill_attribution_20261022.json`。

125个EV金标对已拆：已引用86→109、漏39→16、金额错14→13，匹配内正确率
83.72093→88.07339%；共有4修好、2变坏，新找回25含23对2错，仍9旧错。
WI车辆有5条持续只报4000；PA通用项修对4条，不能说所有金额分支已学会。
报告`Run03_B8_complete16_value_error_on_new_vs_shared_citations_and_all_law_contexts_20261022.json`。

教师15次新鲜返回222534input/2374output、63.106秒。64实际金标/父观察/推理和
上批两组实送8+6反馈引用均核同a232；仅CREATE一条WI EV规则，含独立资产对
16000上限及共同配偶32000上限，其他原字段保持。拟7条bank3387b5b450f4b9107c9738562fa224915bb4405ff329ca8f113fc05d0e9c76e7
尚未准入；连通EV:FEDERAL+OREGON+PA+WI当前12/旧64来源受保护，全部128
来源/256任务仍完整回放。报告
`Run03_B8_teacher1_actual64_B7_final_parent_bounded_real_feedback_and_proposal_delivery_20261022.json`。
下一证据：完整C1（已有线程程序`Run03_B8_C1_complete768_audit_program`仅准备）、
必要C2、唯一B8最终库和原ACE45接续。不看C1部分分数，不热改主协议。
11:30核对实际11:34：160输入/160回答/84原始引用全stop0parse，原3句柄与绑定
保持，A40 25009/49140MiB、97%，366预约/1797、15教师，ACE未开始。证据
`hourly1130_Run03_B8_actual_B7_final_control_delivery_health_and_original_bindings_20261022.json`。

## 成本、备份与论文边界

截至八批首答/教师1返回的固定阶段成本：1131真实8B生成/1131 HTTP，全部stop；
7466268输入/3140381输出tokens。15次新鲜教师3232522输入/51361输出，
reason35912已包含输出；响应耗时1132.442秒不是GPU小时。明确不含在途B8 C1，
也不含静态/ACE、早期失败研究或部署。当前实时调用数继续增加，不能混用口径。
报告：`Run03_complete_first8_plus_teacher1_phasecut1131_15_cost_20261022.json`。
11:34共享账本366预约/1797，历史350前缀未动；旧前缀hash使用原默认JSON序列化，
不是compact canonical csha。首次错误比较仅是审计器序列化错误，不是账本损坏。

最新完整双盘检查点为11:42:45的9381成员八批首答档：371源码数据、1131原始
生成/15教师、全部已完成B1–B7阶段的原始输入/回答/候选/发布与B8完整160位，
125对金额分解、全部32精确输入复用归因（新IL负差也保留）、八批46点曲线、
当前索引和完整历史正文。保全前后371/381/50packages及原三句柄不变；
只有七次最终发布，不含在途C1性能或ACE/TEST结果。
收据：`Run03_complete_first8_value_exactwire_attribution_teacher1_curve_and1131_cost_preservation_20261022.json`。
vdb档SHA `1c592cd142b1adcf7017077ab36c5f773d3c6a0150b84c5f4929ba3989fe24fe`；
root档SHA `8c7ed989a0b56af57f632cbbd0e1e2e6188ba97019b6233647f5121cca457773`。
88537保全正常退出0，不再轮询；11058是唯一当前只读观察，11:43:39仍核C1至253、
1142生成/15教师，无C1完整决定或B8最终库。本轮没有额外模型小测、热改或重启。
设备64528：`/media/sangfor/vdb/legal-skill-backups`；64517：
`/home/yndx/hhy/legal-skill-rootdisk-backups`。不删除旧档；各gzip各自hash可能不同，
按真实成员字节校验，不因容器hash不同误报损坏。不盲拷活动progress/账本/半写JSON。

B7的102个目标资产-法条对中，已引用60→88，金额错6→13：其中4个共有正确
金额变错，不能只称覆盖扩大。另有TRAIN283公司用途与所给一般个人用途条款/
标注(b)(d)的字面张力，法律错误尚未专业裁定。保持原案/标签/评分，不把benchmark
分数说成专家法律准确率，不宣称所有教师法律主张都正确。

[最终分析计划](research/OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md)仍有效：
主方法/ACE各三次独立一致学习seed45/145/245，静态7条/2411tokens尚无性能；
必要whole-bank/first-commit消融为独立学习，不以手删末库冒充。仅ACE45已排队。
128来源配对cluster bootstrap20000次，八主比较/四次要比较，保留有害案例与实际成本。
SkillCommit是必须引用的近邻；没有作者原实现/已授权原编码服务，不冒称复现、
胜SkillCommit或SOTA，即便胜ACE也不越过这个边界。

封存IID128 TEST仍未读语义/预测/标签/结果；只知字节hash
`6a5f72559a021d425d5b6ee41ba19f1a8e10d7da1ac11e0725d469a281c5164d`。
完整方法/矩阵/各次配置/末库须在首次TEST预测前冻结；不据TEST继续调优。
方法稿`paper/manuscript_v1_20261021.md`，正式Results仍PENDING；
证据账本`paper/evidence_and_completion_20261020.md`。当前未证明成熟方法胜出或完整论文达成。
