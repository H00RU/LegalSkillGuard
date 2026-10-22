# 当前Goal执行索引

2026-10-22 Asia/Shanghai，状态依据09:32唯一发布、09:43完整首源投递及09:46原句柄核验。
Goal仍active，完整论文目标未完成。Run03已完成七批学习，原进程正在B8首次遇案。
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
- canonical锁：`artifacts/openexempt_training.lock`。

当前只读观察为原生session **46189**：目标是B8两份完整首答文件均存在；
09:34:09启动，期限12:34:09只结束观察，不结束训练。目标制品优先于main句柄
检查，覆盖主训练自然完成的情况。不再轮询已结束19459、26541、87678，
包装7385/7388也已正常结束；当前无functions包装运行。
下一小时方向核对 **10:30 CST**，不要将观察超时当成重启理由。

## 冻结协议与原始绑定

学习/执行代码仍`6896246`。后续仅文档/离线图脚本提交，不等于改算法。
配置：`configs/openexempt_closed_feedback_public_assets128_20261021_run03.json`，
SHA `8c858d27892f278ee9cdd6c251486ce2080637aa5f01c51d165ecdab5fe2122e`。
frozen371清单SHA `2cc50e6cfe05fb42c230aba570eb43e9fcd41c3287011f77de8291fd89418825`。
09:30 main371/static117/ACE等待381文件及50packages均原样保持。

128固定TRAIN来源181–308，8批各16来源、每源独立EC/EV，共256任务。
custom profile为2–4资产、五州、公开可用法域/start2，不是官方Advanced或OOD。
v14 `direct_statutory_claims`、`legal_scope`、`carry_partial_and_refine`；
EC/EV独立直接回答，无EC答案向EV传递。公开资产/法条引用对所有角色相同。
库上限4096完整序列化tokens；每批至多2次教师提案，不是只允许一次技能操作。
允许CREATE/UPDATE/DELETE/MERGE/NOOP；不强制增长或收录。
教师gpt-5.6-sol/high，实际当前16+选旧16来源/64任务标签、真实父观察和有界失败反馈。
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
| B8 | 待完整首答 | 待完整首答 | 待学习完成 |

B7强空库EC58.125/EV61.5625%；在线EC78.54663/EV80.75521%，来源9好2坏5平。
本批所有EC请求与自身B1精确相同，因为此前唯一后B1 EC变化在Oregon，本批无Oregon。
不能由EC持平推断模型不可能再学EC。B3–B7的80新来源相对B1 EC+0.78373/
EV+10.37426pp，含按设计相同B2的96来源为+0.65311/+8.64521pp；均是单学习器TRAIN。
不同批次案件不同，裸分下降不能直接当同案遗忘，也不能称单调改善或统计显著。

机器曲线：`artifacts/research/openexempt_legal_scope_20261020/Run03_learning_curve_complete_prequential_batches_20261021.json`。
新固定快照：同目录`Run03_learning_curve_complete_first7_and_unique_B7_final_snapshot_20261022.json`。
七批PDF/PNG在`artifacts/research/learning_curves_20261022/Run03_B1_B7_prequential/`；
40首答点完全不动，图的发布状态为绘图当时快照；不重画旧图或补B8零值/虚构CI。

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

B8原进程09:46已到来源295；首源293为IL，09:43全部EC/EV角色10输入/10回答
均核同，skills收到真实a232，六原始生成全stop/零解析错，EV未泄漏被拒修改。
不是完整B8结果，未读部分B8评分或标签。
下一步只等B8两份完整首答文件，核16来源/160逻辑记录、实际库、原始解码/评分和成本；
随后本批有界学习、B8唯一最终发布，再按原等待器接ACE45。
线程存储已准备`Run03_B8_complete160_newcase_audit_program`，不能将准备当完成。

## 成本、备份与论文边界

截至唯一B7终态的固定阶段成本：1047真实8B生成/1047 HTTP，全部stop；
6913968输入/2907578输出tokens。14次新鲜教师3009988输入/48987输出，
reason33910已包含输出；响应耗时1069.336秒不是GPU小时。明确不含在途B8，
也不含静态/ACE、早期失败研究或部署。当前实时调用数继续增加，不能混用口径。
报告：`Run03_complete_B1_B7_unique_final_phasecut1047_14_cost_20261022.json`。
09:30共享账本365预约/1797，历史350前缀未动；旧前缀hash使用原默认JSON序列化，
不是compact canonical csha。首次错误比较仅是审计器序列化错误，不是账本损坏。

最新完整双盘检查点为09:45:53的3604成员B7唯一终态档：371源码数据、1047原始
生成/14教师、两候选全部1344位、EC实际收益/EV语义失败、首源293全部10投递、
七批固定首答/发布快照、新当前索引与逐字保留1237行历史正文。保全前后371/381
绑定、50packages及原三句柄不变；不含B8完整成绩或TEST。
收据：`Run03_B7_two_complete_candidates_final_EC_only_B8_delivery_and1047_cost_preservation_20261022.json`。
vdb档SHA `269ce1d601292844bafa24519839c9125a19015b738b2e3a90975aa4c3421868`；
root档SHA `7ad93f4f2d48a90d8f82c8fe328af9ca29b5d5eeda2f9f6173ed902738e97e8f`。
4865保全正常退出0，不再轮询，46189是唯一当前只读观察。
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
