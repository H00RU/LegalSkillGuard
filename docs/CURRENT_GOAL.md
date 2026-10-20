# 当前Goal执行索引

更新：2026-10-21 Asia/Shanghai，B2最终发布完成、B3新案首遇进行中。Goal active，尚未完成。
本索引用于定位，不以旧游标、状态文件或锁单独证明进程存活；每次续接先核
实际systemd/PID及start ticks，再读当前progress和不可变批次/发布记录。

## 完整目标不缩减

重整并持续推进法律垂直技能学习研究：以现有单实例冻结Qwen3-8B为执行者，
证明可演化技能在后续新案及最终隔离测试上相对同工具权限、同推理预算的
强空库和可信经验学习方法产生可复核净收益，并形成有说服力的论文证据。
法律任务与主方法不预先锁死；优先完成OpenExempt EC/EV的连续多批机制验证，
检验真实行为修正、训练内反例重放和技能增删改管理。候选无新案净益时查实际
断点，不以机械单调曲线或技能数量增长为成功，也不硬拖完整无效训练。
真正完成实现、连续学习、强对照、独立重复和隔离测试才算完成，不是单批正点差。
继续依据当前代码、9月27日起本会话历史及师兄两个skill作实证审查，避免整库
提示调词、换名复跑旧失败或陷入单案局部调试；历史用于追溯，当前真实状态优先。

用户追加要求见[生效补充](research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md)。
其旧小时游标属于历史，以下当前入口优先。不要恢复客户路由、32B或早先旧Run。

## 唯一实际训练与冻结边界

- 项目：/media/sangfor/vdb/legal-skill-evolve；用户入口/home/yndx/hhy/legal-skill-current。
- Run：`legal_openexempt_closed_feedback_public_assets128_20261021_run02`。
- unit：`legal-openexempt-closed-feedback-public-assets128-20261021-run02.service`。
- 主PID1047861，start ticks452655332，2026-10-21 02:13:55启动。
- 模型unit：`legal-qwen3-8b.service`；PID3613253，start ticks446037091。
  同一Qwen3-8B/bf16，revision b968826d9c46dd6066d109eabc6255188de91218。
- 后继等待unit：`legal-openexempt-main128-to-ace128-20261021-run01.service`，
  PID1532114/start454636337，07:44:05启动；它是等待进程，不是第二个模型或训练。
  仅在本Run完整八批128案终态及双盘核验后接续ACE；主训练早停/失败则不接续。
  同PID在exec后会成为ACE工作进程，须核actual argv、starting_ACE128_once及
  目标progress；旧queued.json不能单独证明当前仍在等待。
  若需修主链路，先核实际phase并取消尚在等待的接续，保全后再做源码转换。
- 配置：`configs/openexempt_closed_feedback_public_assets128_20261021_run02.json`，
  SHA00f085e343436d5028e5b81f7e1a0f5de3c4a2cb01c3d392ea0e3b04f51e1e50。
  对应frozen清单388文件不得热改；实际学习/执行源码仍为13e67fa的绑定字节。
  新增未绑定对照配置/文档不等于更改运行方法。模型也不重启、下载或替换。
- 唯一canonical锁：`artifacts/openexempt_training.lock`。不与当前训练并行推理。
  NCCL Broken pipe警告曾与真实持续生成并存；必须核实际服务/请求，不能据警告重启。

实时入口是本Run的`progress.json`、`batch_summary.json`、`candidates/`及
`publications/`，不是本索引的静态时刻。观察会话到时不是训练终止；重新核同一
真实句柄，不因capacity提示、观察超时或旧PID记忆另启一轮。

## 当前方法与数据

`direct_statutory_claims`版本14、`legal_scope`、`carry_partial_and_refine`。
从空库开始，8B权重不更新；只以技能改变其后续回答。所有臂共享公开字面资产
引用、可读法条标签、给定法域与原题面；8B自己判断适用法条和金额。
无算式解释器、隐藏答案工具、语义修补、第二模型或fallback，operators为空。

整批全部首遇预测落盘后才给教师本批TRAIN标签。教师为已有gpt-5.6-sol/high，
每批至多两提案，可一次多项CREATE/UPDATE/DELETE/MERGE，允许明确NOOP。
部分通过后可按真实父库继续修订；每批只作一次最终发布。整库4096 Qwen tokens。
全已见TRAIN重放、原EC/EV和完整EV门槛、组合请求必须已有原始观测的条件不变。
这是TRAIN优化，不是独立验证，不保证逐案/逐声明或未来无损。

数据是原生OpenExempt固定构造的128来源/256项EC与EV，八批各16来源，
ID181–308、seed2026102101。不是早先多轮咨询重构的128案，也不是两个弱模型编案。
packet：`data/packets/openexempt_closed_feedback_public_assets128_20261021/inputs.json`，
SHAef17d71b8b12f433f73d8c41afb04c506346614e69891cde66840d6daf6c7c45。
2–4资产、五州、夫妻比例0.5、给定AE法域，无额外干扰；不是官方Advanced原配置。
EC是法条识别，EV同时给出法条及金额；同源两任务不是两个独立数据集。
评分器和金额容差不改，夫妻上限的标注语义风险保留披露，不当作真实法律建议。

## 已确认成绩与当前未知

| 观察 | EC F1 | EV F1 | 边界 |
|---|---:|---:|---|
| B1空库首遇 | 63.45% | 66.35% | 16来源、学习前 |
| B1最终库同案重答 | 92.04% | 88.33% | 看过标签后的TRAIN，不是新案 |
| B2同案强空库 | 68.71% | 64.51% | 16个新来源，本批反馈前 |
| B2使用B1最终库 | 96.34% | 89.88% | 本批反馈前，已核全部160逻辑记录 |

B1最终6记录/1995 tokens，bank SHA
b6035a16001c5acfddcc630bc99c2e4d10a982d8e32e5e1db6646d596e310904。
B2完整EV为63.83%→88.61%；32项任务23好0坏9平，不代表逐声明无损。
111目标金额声明正确50→92、漏报57→15、错金额仍4；6条原本正确声明被漏掉。
48条修复中43条是通用备选条款，6条损失全是具体条款；这是描述性拆解，
不能把计数比例等同F1归因。15条EV漏报中的14条在另一次同库EC回答里已找到。
当前剩余重点是同时列全法条并执行金额规则，不再笼统归因客户路由或缺少标签。

B2首遇时的在线库与本次B1冻结库相同，两臂持平是预期；继续更新的价值要由B3以后
对自己的B1冻结库证明。B2教师确实收到64项已见任务的真实标签和当前父答案，
历史失败的8条参照已刷新；提出5UPDATE、仍6记录，提案hash
5bf8efe2fae41f10ef08a8cd3bd6f01c886338d51fa2bb55cac9673739586d06。
候选1已完成64任务重放，只有EV:ILLINOIS被采纳，过渡父库a8f96d42，仍6记录。
全部240目标金额声明正确200→206，原200条全部保持，新增1条错金额；完整
整库提案却损失27条原正确声明。作用域采纳避免了本次这些损害，不保证未来。
这是TRAIN重答与同一提案的真实组合证据，不是已完成的整库算法消融或新案收益。
候选2真实收到64任务标签/当前父答案及16条刷新参照，只提1UPDATE亚利桑那。
完整重放使B2金额F1从90.92%降到87.80%，被拒绝；失败和7次真实生成成本保留。
B2最终于06:59:30发布a8f96d42，仍6记录、1989tokens，只改变伊利诺伊记录。
此库的B1/B2已见重答EC/EV分别92.04/90.93%与96.34/90.92%，均是TRAIN，
不是B2首遇或TEST。B3已自动用此库继续，并保留本次B1固定库b603作为真实控制。

不可变证据在`artifacts/research/openexempt_legal_scope_20261020/`：

- `MAIN128_complete_B2_160native_newcase_effect_20261021.json`：完整请求/解码/原评分及成本。
- `MAIN128_B2_all_native_EV_claim_transitions_and_remaining_errors_20261021.json`：全部111声明。
- `MAIN128_B2_teacher1_actual64labels_parent_refs5UPDATE_notyetadmitted_20261021.json`：真实教师输入。
- `MAIN128_B2_candidate1_complete64_scoped_rescue_all240EV_20261021.json`：完整候选及声明损益。
- `MAIN128_B2_teacher2_actual64labels16currentrefs_oneArizonaUPDATE_20261021.json`：真实续改父库/反馈。
- `MAIN128_B2_candidate2_complete64_rejected_Arizona_all240EV_20261021.json`：完整失败候选。
- `MAIN128_finalB2_210native4teachers_actualcost_and_B3_delivery_20261021.json`：正式发布、成本及B3送达。

下一步等B3完整16新来源的全部首遇输出，对强空库和本次B1冻结库核原始评分、
实际送达及损益；这是继续进化是否有新案价值的首次非平凡比较。只读观察句柄
77603，旧40295/22862已完成，不复活。未完成批次不挑好案计分或按单案改方法。

B3公开输入的事先核验：与本次B1固定库相比，全部16项EC和11项EV请求完全
相同，只有5项伊利诺伊EV请求改变。因此EC持平是预期，不解释为未送达技能；
主均值仍包含全部16来源，不能只报5项受影响子集。尚未读取B3部分分数。
另已核B2整提案23条漏报中21条在其独立EC回答出现，金额绑定仍会错；不是
标签漏送、协议或截断。教师2共225284输入tokens，以轨迹而非法条字符为主。
ScienceClaw原代码启发的下一失效假设是显式历史修复前/后对照：本次4项改善
中的旧受控轨迹未直接送入教师，只有更新后父答案。3项完全正确、1项仅改善，
不能都称通过。此补强尚未实施；先看B3完整新案，不为假设改当前冻结协议。

## 必要对照、消融与后续执行

现有静态法条控制Run02只编译：6记录/2425 tokens，零案件、轨迹和标签，尚未
评估，不混入主库。首版结构失败和两次教师成本均保留，不按效果重编译。
旧32案ACE13已中止且不完整，不能充当正式基线；类型适配修正已在13e67fa。

| 未来配置 | 真实状态 | 后续累计教师天花板，不是实际消耗 |
|---|---|---:|
| ace_public_assets128_20261021_run01 | 同128案/接口14，已后台排队等待，未freeze/训练 | 3317 |
| whole_bank_public_assets128_20261021_run01 | 现有整库策略，单次seed45消融，未freeze/启动 | 3349 |
| first_commit_public_assets128_20261021_run01 | 不跨批携带/部分采纳后不续改，单次消融，未freeze/启动 | 3381 |

配置均在`configs/openexempt_*.json`，协议分别为
`research/OPENEXEMPT_ACE_PUBLIC_ASSETS128_20261021.md`和
`research/OPENEXEMPT_PUBLIC_ASSETS128_MECHANISM_ABLATIONS_20261021.md`。
当前账本上限仍1765。未来只能在先前绑定任务实际终态、双盘保全并保存旧账本
之后扩额，保留全部历史下界和预约。只有上述一次性ACE等待，不重置账本。
其接续源码和真实queued/backup记录在`artifacts/launches/openexempt_main128_to_ACE128_20261021*`。
接续前核满256项首遇、末库、终态两盘文件与重要记录档内字节、392项当前
source/data/environment pins；不合并代码、不重启模型、不读TEST或额外GPU资格生成。
源码或模型变化、已有后继freeze/Run、主训练不完整均停止接续并保留失败。
排队核验时账本上限1765、已知预约下界1573；3317仅在成功终态后生效，不是实际消耗。
两项消融与三次独立学习尚未自动排队，仍未完成。
ACE库8192较本方法4096大，不称相同记忆/总训练预算；first_commit也不是关闭
所有反馈或等实际计算的纯信息消融，须报告不同调用量。

最终评测/来源配对统计的改动仅在现有隔离worktree
`.venv/evolution-control-20261020.qLon9T`，branch
`prospective-static-frozen-control-20261021`，HEAD6caec6c，尚未部署。
它包含真实静态库来源核验、三次学习seed45/145/245检查、按来源同时保留EC/EV
配对的预定bootstrap，以及两项单seed策略消融的独立次要比较族；41项小CPU
检查不算性能。c99排序反馈修复也未部署，
不能为假设问题停掉当前正向运行。不得把隔离实现或配置写成正式实验完成。

## 隔离TEST与论文证据缺口

IID128 TEST recipe与packet已封存，语义/预测/评分未打开；官方HF TEST也未打开。
仍须完整128流、后续更新相对B1的收益、可信经验方法与静态对照、独立学习
重复、必要机制消融和近邻创新核对，固定完整末库矩阵及统计实现后才运行TEST。
主方法和ACE计划各三次从空库学习，seed45/145/245；当前Run02只有算法保持
一致才可计入。单次消融不冒充三次，复制空库预测/精确缓存不扩大独立样本数。

分析计划：`research/OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md`。来源cluster
bootstrap只给实际库和固定解码条件下的区间，不保证学习算法总体稳定。
[SkillCommit原文](https://arxiv.org/html/2608.15165v2)已包含标签辅助修复和源重放，不能据此宣称原创或用不同设置的
原文裸分宣布SOTA；公开共同渲染提交单位的额外价值仍需真实消融与同条件对照。

## 持续执行约束与历史

不另设验证集；不挑案例/seed/旧好库，不拼新旧协议曲线，不修原答案或放宽原
评分。不新增付费服务、嵌入模型、32B/第二实例或无关框架。失败、成本、源码
双盘保全。明显系统性问题按实际证据停止对应训练，保全终态后修根因并用新Run，
不擅停模型。普通慢调用、观察超时、单个负点不是丢弃整轮的理由。

每小时按真实Asia/Shanghai时钟复核生效补充的五项。最近计划07:30、实际记录
07:30:46.000，下一08:30；批次事件不冒充额外小时检查。后台systemd训练
不依赖对话在线，观察器不是独立唤醒产品。无证据时等待具体活进程，不反复B1。
师兄skill用于真实失效假设、公平性和成本，不用于固定创新数或隐藏借鉴。

旧1204行索引完整归档到
[历史索引](research/CURRENT_GOAL_HISTORICAL_through_20261020_1901.md)，
归档前原字节另有双盘副本。历史内容仅供追溯，不作为当前训练入口。
