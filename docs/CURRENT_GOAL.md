# 当前Goal执行索引

状态快照：2026-10-21 Asia/Shanghai 13:30:37。Goal active，完整论文目标未完成。
先核真实PID/start ticks和实际argv，再读progress；状态文件/锁或本索引不单独证明存活。
旧Run02及旧等待器不得恢复。其历史完整保留，当前唯一主训练为下述Run03。

## 完整目标不缩减

以单实例冻结Qwen3-8B，证明可演化法律技能在后续新案及最终隔离测试上，
相对同权限/同推理预算的强空库、可信经验方法及自身B1库产生可复核净收益。
优先OpenExempt EC/EV多批验证、真实行为修正、反例重放及技能增删改管理。
不用机械单调曲线、技能增长、启动成功、单批胜空库替代完整证据。
必须完成实现、连续学习、成熟对照、独立重复、必要消融和隔离TEST。
数据/任务仍服务于法律论文，不因已投入时间锁死；也不遇单个负点就换名重启。
用户补充在research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md，继续生效。
师兄两个skill用于真实失效假设、公平性和成本，不采用隐瞒借鉴或预设胜出。

## 当前真实运行

- 项目：/media/sangfor/vdb/legal-skill-evolve；用户入口/home/yndx/hhy/legal-skill-current。
- 主Run：legal_openexempt_closed_feedback_public_assets128_20261021_run03。
- unit：legal-openexempt-closed-feedback-public-assets128-20261021-run03.service。
- PID1721740/start455413980，09:53:42启动；11:57:46已完成B1唯一最终发布和
  真实B1冻结快照，11:57:47自动接B2。13:07:11已完成B2全部新案首遇并进入教师；
  13:30:37同PID/start仍在，167次真实生成、3次教师响应，b2_candidate1_replay，
  当前已发布库仍5条/1591tokens。没有重启或沿用旧好库。
  第一候选已完成15/64任务重放，source188；完整决策和B2最终发布尚不存在。
  12:30原main/model/waiter PID/start ticks、371/117/381绑定及50packages均保持。
- B1全部160逻辑首遇为32真实调用和128精确请求复用，原EC/EV63.44990/66.35417%。
  两轮TRAIN修订后实际发布库的本批重放83.24901/80.78621%，不是新案/TEST分数。
  最终bank574af7a6d3a5f155d45aebeefb7f620884cbe557a2e5f91914bbfdd3f2eb5118。
  自身B1快照精确等于这一唯一发布，早于任何B2输入；不得改取最佳早期库。
- 配置configs/openexempt_closed_feedback_public_assets128_20261021_run03.json，
  SHA8c858d27892f278ee9cdd6c251486ce2080637aa5f01c51d165ecdab5fe2122e。
- frozen清单371文件，SHA2cc50e6cfe05fb42c230aba570eb43e9fcd41c3287011f77de8291fd89418825。
  学习/执行代码提交6896246；后续仅文档或未绑定配置更新不等于改变算法。
  相较旧388少的是旧启动附件、未被主运行调用的实验入口/ACE资料，不是漏掉运行依赖。
- 单8B unit legal-qwen3-8b.service，PID3613253/start446037091，原Qwen3-8B bf16
  revision b968826d9c46dd6066d109eabc6255188de91218；没有重启、下载或替换。
  32768上下文/8192输出、thinking开、temp0.6/topP0.95/topK20/seed45不变。
- canonical锁artifacts/openexempt_training.lock，不并行抢GPU或另开资格生成。

实时入口：本Run的progress.json、batches/、candidates/、publications/。
NCCL警告曾与真实持续生成并存，不据警告或观察超时重启模型/训练。
旧观察会话36819、17852、45630、82219和2299已正常结束，不复活；2299于13:07:14
看到B2两份完整首遇制品后退出0。当前只读会话9771等待B2候选1完整TRAIN决策，
每轮核PID/start ticks；其两小时观察期限不等于主训练期限，不能据此重启。

## 当前方法与修复边界

direct_statutory_claims接口14，legal_scope，carry_partial_and_refine，从空库开始。
同一128来源/256任务，ID181–308、seed2026102101、八批各16来源。
packet data/packets/openexempt_closed_feedback_public_assets128_20261021/inputs.json，
SHAef17d71b8b12f433f73d8c41afb04c506346614e69891cde66840d6daf6c7c45。
2–4资产、五州、夫妻比例0.5、给定AE、无额外干扰，不是官方Advanced原配置。
EC识别法条，EV直接输出法条/金额；一源两任务不算两个独立数据集。
此前Run02已运行相同TRAIN前三批及部分B4；当前学习器从空库重启，首遇/新案仅指
本Run学习器尚未见到，不是研究者未见，不构成独立重复或隔离泛化证据。
律师的actor_payload/direct_case_input AST、数据和生成配置已对旧源核验不变。
无EC→EV串联、解释器、第二模型、答案修补或fallback，operators仍为空。

原生EC/EV precision/recall/F1与金额匹配不改。原EC在空法条目标上无论正确为空
还是误引都得0，可能把有害修改误当原F1保持。既有完整EV审计现扩至EC；
两任务候选分量和最终整库均保护当前/历史原F1、完整输出F1、负目标/未计分资产
预测声明计数及格式错误计数。严格当前改善允许F1提高或上述真实错误计数减少。
这是TRAIN优化，按群体汇总，不保证逐案/逐声明/未来无损，不替换论文主指标。
配置中旧original_full_family_and_full_EV_acceptance_unchanged字段仅指这些原非退化
约束仍保留，不能理解成整体准入算法未变；新admission_contract与协议决定本版。
协议research/OPENEXEMPT_COMPLETE_OUTPUT_RETENTION_PUBLIC_ASSETS128_20261021_RUN03.md。

每批全部首遇预测先落盘再给TRAIN标签；教师已有gpt-5.6-sol/high，至多两提案，
一次可多项CREATE/UPDATE/DELETE/MERGE或NOOP；库总4096tokens，不强迫增长。
所有已见TRAIN重放/原始请求组合覆盖和每批一次最终发布保留，没有验证集。
自身B1控制固定第一次最终发布，只评测，不送教师/准入，不取第一非空或最佳库。

B1教师1于10:39:05返回5 CREATE，父库为空，候选hash25eec0b9ecfdf02a4ca7210e422d73614fb252c2bd9f132eacaf86d1f629181e。
已逐项核32任务的原TRAIN目标、父/空库答案、原分数/完整输出/负资产计数和真实
推理尾部；全部确实送达教师，不含未来源。输入123777/output4277 tokens、93.05秒，
reasoning2514为output子集；1次新鲜响应，无工具事件。10:56已核16个完成候选请求
的实际技能投递、原始messages/schema和不变解码；不把投递等同于遵循或有效。
五记录分别FEDERAL/OREGON/PENNSYLVANIA/ILLINOIS/ARIZONA，均EC+EV且operators空。
证据Run03_B1_teacher1_full32_actualfeedback_partial_delivery_20261021_1056.json。

11:15候选1的完整32项TRAIN重放：父EC/EV63.44990/66.35417%，全提案71.80060/
75.57788%，实际组合71.80060/76.61954%。EV:ARIZONA未通过，其他五坐标通过；
整库组合复用精确已见wire后再核最终整库门槛，不做逐案答案择优或fallback。
完整EC/EV分别75.42097/75.97388%，负目标/未计分资产声明仍各1；不是全部错误已解决。
96记录槽原主值与完整分重新核算，不是96次独立生成。残余主要是漏法条：EC47、
EV44，其中EV31条联邦通用替代仍漏，金额错2；不能把技能送达等同于执行成功。
诊断Run03_B1_candidate1_complete32_native_scores_and_claim_failure_diagnostics_20261021.json。

教师2真实输入逐项核32目标/实际组合父答案、原始requests、真实推理引用及8条
未采纳部分的反例。父hash9fcab02d43e4f1588a2d487c30c70c994c91c551d28025d3e3b246edaac6f037，
11:17:03返回5 UPDATE，无CREATE；proposed85daaa985a96408ee190d8f11edc1496b2913066016f5990d38d13d971ac8890。
138324input/5113output tokens、104.642秒，reasoning2843为output子集，无工具/缓存。
11:19先核2个完成的第二候选wire；32项第二重放未齐，不报完整分或发布成功。
候选内容可能仍把EV的法条选择写成已有前提，这是待用自然重放反馈检验的内容假设，
不是已证唯一原因，不据单例热改教师/执行器或重启B1。

11:57第二候选完整32项：父EC/EV71.80060/76.61954%，全提案83.24901/70.54067%；
只接受三个EC坐标及EV:ILLINOIS，最终实际组合83.24901/80.78621%。EV:ARIZONA
因完整输出/额外误引不通过，EV:FEDERAL+OREGON+PENNSYLVANIA+WISCONSIN因原F1
及完整F1下降不通过。最终EC负资产误引0、EV负/未计分声明1，格式错误0；所有
96次B1物理生成均stop，没有以截断或格式修补隐藏坏提案。
最终5条：ARIZONA仅EC；FEDERAL/ILLINOIS/OREGON/PENNSYLVANIA各EC+EV；operators
全部为空。CREATE5后五个记录都发生任务内改写，但未采纳上述坏EV部分；库没有
强制增长，也没有发生DELETE/MERGE。剩EC漏法条23、额外2，EV漏42、额外3及
未计分1；EV已计分法条的金额错0，仍漏31条联邦(d)(5)替代。主要剩余断点是
法条枚举/选择，不应再笼统说金额不会算，也不将此当已证唯一执行因果。

B1共96真实native/96HTTP、630165input/251015output tokens；教师2响应2尝试，
262101input/9390output，reasoning5357为output子集。11:58发布/实际B1快照逐项
核验通过。12:02另核B2 source197全部10逻辑首答，真实wire/投递ID符合这一库，
在线与自身B1完全相同，未打开B2 Gold。该案EC投递AZ技能、EV无合适已发布块，
所以EV为正常空投影，不是失败时换答案或fallback。
证据Run03_B1_candidate2_complete32_native_scores_and_claim_failure_diagnostics_20261021.json、
Run03_B1_actual_final_publication_own_B1_freeze_and_measured_costs_20261021.json和
Run03_B2_first_source_actual_B1_delivery_no_gold_20261021.json。
12:07将本批所有96物理原始生成、完整B1各阶段逻辑输入/输出、两教师、真实发布/
自身B1快照和B2首案投递证据共706成员逐字节双盘保全，设备64528/64517。
各盘归档SHA分别6df56e6e5765bb91db877901d16869e7a4a3007fbfcad881e0f97fad08de89ee
与aef7bb79d97895afcbdc6c46898127c7fcc5c816a48e0f709f86863015d2275a；gzip容器哈希
可以不同，两盘各自核真实成员与各自收据，不据此误报损坏。保存时371/381绑定不变。

## 为什么停止旧Run02，旧结果如何使用

旧PID1047861于09:36:18按信号设置的工件安全边界停止，failure为
InterruptedError('Operator stop at artifact-safe boundary')，不是服务崩溃。
331次生成全部stop，2188655输入/903092输出tokens；6教师1142901输入/24343输出
（reasoning15449属于output，不另加）。B4只留下229/230部分预测，不评分、不拼曲线。
2571终态成员和388旧源绑定在两盘独立逐字节核验后才修改源码。

旧B2新案：强空库EC/EV68.71/64.51%，B1技能96.34/89.88%。
旧B3新案：强空库64.70/60.79%，在线93.56/87.50%，自身B1也是93.56/87.50%。
这些仍是开发证据，不是Run03分数、TEST或持续进化证明。
旧B3 C1修手链却损伤工具箱，被拒；C2只采纳AZEC，b822、6记录2051tokens，
当批EC93.56→95.64%，旧案原EC94.19%不变。但182吊坠新增戒指法条，旧完整EC
97.34554→96.72054%；全48完整EC净值持平，TP327→328、FP4→5。
正是这个通用计分/准入盲点促成修复，不是按个案改法条或改原答案。
288旧父/提案/发布记录重新核算，原主值全部不变、旧完整EV也不变；新准入会拒绝
该候选。这是回顾性根因复核，不是新算法已经学得更好。
79项现有CPU边界检查8.21秒通过、ruff通过，0新测试文件/0额外GPU资格生成。

关键证据位于artifacts/research/openexempt_legal_scope_20261020/：
- MAIN128_B3_C2_complete96_scopedAZ_published_all288_nativechecks_20261021.json
- MAIN128_B3_nativeEC_negative_target_blindspot_all48_20261021.json
- Run02_artifact_safe_stop_EC_blindspot_complete_preservation_20261021.json
旧完整B2/B3首遇、失败、教师输入/差分及原始请求也在该目录并双盘保全。
旧Run02不得与本版后两次学习拼成三重复。

## 真正后台等待的ACE

- unit legal-openexempt-main128-run03-to-ace128-20261021-run02.service。
- PID1738522/start455481667，10:04:59启动；10:48已重核真实argv，尚未exec为ACE。
- script artifacts/launches/openexempt_main128_run03_to_ACE128_20261021.py。
- 制品目录artifacts/launches/openexempt_main128_run03_to_ACE128_20261021_v2/。
- 381 source/data/environment pins不热改；目标ACE128尚未freeze或训练。
  同PID exec后会成为ACE进程，必须核starting_ACE128_once/目标progress/actual argv。
- 仅Run03完整八批/128源/256首遇、末库、两文件系统终态archive和关键成员、源/
  模型身份及账本核验通过后，在同canonical锁下扩额/freeze/exec一次。
  早停/失败/变化/目标已存在则停止接续保留错误，不重试、不覆盖、不读TEST。
- 原1532114已取消。首个新引导unit run01因旧归档名冲突失败，未freeze/训练/扩额；
  失败源码和制品四成员双盘保全，现用带Run03_v2的独立归档stage，未删除旧归档。
- 若要修改任何绑定源，先确认并取消仍在等待的接续，再保全当前训练并转换。

ACE仍原生Generator/Reflector/ADD Curator与最多三轮TRAIN反思，不用本方法准入。
只修TRAIN成功判定为合法解析且完整FP=FN=0，正确负例不再因原F1<1无谓重答。
ACE8192库较本方法4096大、实际训练调用不同，不称等总计算或完整作者默认复现。
当前账本1797、历史下界1225未重置；11:19为353预约，旧350条前缀hash逐字节保持。
3349只在完整终态后扩，不是实际消耗。

| 后续配置 | 真实状态 | 未来累计教师天花板 |
|---|---|---:|
| ACE128 seed45 | 实际后台等待，未freeze/训练 | 3349 |
| whole_bank seed45 | 未freeze/启动/排队 | 3381 |
| first_commit seed45 | 未freeze/启动/排队 | 3413 |
| main seed145 / ACE seed145 | 只备配置 | 3445 / 4997 |
| main seed245 / ACE seed245 | 只备配置 | 5029 / 6581 |

七份未来配置已重绑Run03/同seed参考SHA；不再指向旧学习算法。
两消融仍只有单次seed45；first_commit不是关闭全部反馈或等实际计算。
三重复共享同TRAIN，独立从空库、日志/教师请求全新，不扩大独立来源n。

## 论文和下一步未完成项

静态盲法条已于10:28:02完成新源Run03零案件编译，7记录2411 Qwen tokens，
bank4809c3b2fe336a682ad36544f036206f158c0890adad4e87bde6eb4fa6502321。
117绑定/50packages和实际公共输入已核，不含案件、标签、轨迹、旧库；与旧静态02
实际SYSTEM、公共输入、schema、model/effort相同，只因共享源epoch变更而重新编译。
三次静态响应含首次结构失败均保留，总56256 input/10248 output tokens、211.898秒。
全部仍无8B预测/性能，不按成绩选库，不进入主方法。新静态终态6成员已双盘保全。
最终评测/统计实现还在隔离worktree .venv/evolution-control-20261020.qLon9T，
HEADf494f18fd9ea8fa5ae3b6d9908103c144df5990a，未部署。已同步当前6896246执行/评分源，既有端到端检查扩为正确空
负资产/误引两种情形，原分与完整EC/EV分别保留；43个评测检查及共111项相关CPU
检查通过，ruff通过，未产生GPU/教师/TEST调用。11:38另补同类三重复的实际生效
学习策略/反馈/容量/提案或反思轮数/教师/除seed外生成设置一致性；累计共享账本
上限与运行审计元数据不要求相同。现47个评测检查7.52秒通过、ruff通过；六份实际
配置协议检查通过且13个执行源与root逐字节相同，不表示未来运行已完成。
这些是最终评测约束，不是当前低分的新根因；已收尾，不继续扩写测试/评测框架。
隔离worktree未跟踪官方cache，
测试命令显式解析到既有固定版本官方依赖，保留最初缺依赖及symlink-origin失败。
未来须以真实完整末库固定矩阵；不热合并当前371/381绑定代码/测试。c99排序修复
也未部署。当前固定8批、每批至多2提案不涉及c99排序，不为此改活跃源或重启。
静态完成不等于完成对比，CPU检查不等于论文实验。

12:19定向核对EV剩余断点，非新增通用测试：真实题目与教师任务说明均明确要先
找全适用法条再算值，给定步骤仅AE，没有当前EC答案。最终181_EV真实wire只收到
EV块，未收到该技能的EC块；联邦EV块从eligible pair为前提的计算开始。C1父库、
C2全提案、最终库均仍漏31条(d)(5)；C2全提案另新增9个非IL金额错，IL原2错已修，
最终组合金额错0。B1最大prompt7036、输出8192、context32768，96次均stop，
不能再用任务/标签没送到或本批截断解释这组遗漏。
这将先前的“EV选择步骤不完整”假设具体化，仍非唯一因果证明。可能的后续最小
修订仅澄清作者的任务可见性与独立执行契约，要求EV先逐资产枚举，再计算，并
保留已正确的计算片段；现有文本技能可表达/共享过程，不增加router、fallback、
固定技能类型或EC答案串联。目前未实施；继续看自然教师修订，不热改源。
证据Run03_B1_EV_actual_task_visibility_no_truncation_and_residual_enumeration_seam_20261021.json。

13:07:11 B2全部160逻辑首遇已保存才读取本批TRAIN标签/启动教师。16新来源197–212，
原EC空库68.70536→技能83.67684%，EV64.51389→74.44940%；均值66.60962→79.06312%，
净+12.45350pp，32任务help18/hurt2/tie12。EC完整输出69.99382→86.83837%，EV
63.83432→74.51697%；负目标/未计分声明EC1→0、EV1→1，格式错误均0。60次真实
请求均stop，390655input/144355output tokens。实际messages/schema/库hash/投递
和原分、完整分均重算通过，不是同批重答。在线与自身B1同答案/raw/分数，是本批
按设计完全相同的库，不是继续进化已获额外收益，后者须从B3检验。
EC漏法条52→26；EV漏法条57→40，其中技能EV仍漏28条(d)(5)，另2项金额错，
完整TP69/FP9/FN42。两项原F1负收益为202EC和205EV，未删除或换案例。
证据Run03_B2_complete160_new_source_native_grade_actual_wire_and_B1_control_20261021.json、
Run03_B2_complete_newcase_residual_and_actual_teacher64_labels_current_parent_20261021.json。

B2教师1实际输入64项标签/父答案/真实推理引用（16当前+16历史来源），两份B1
部分拒绝各8见证均以当前最终B1为参照，未送后续案例。13:09:34.883返回新鲜响应，
229061input/6239output tokens、143.175秒，reasoning3998已含在output，无工具事件。
UPDATE4+CREATE1，提案6条但还未准入；联邦EV显式加入逐资产独立(d)(5)并保留金额
上限，另修PA/OR/IL和共同宅地值，属于教师自然修订，不是研究者手改库。提案schema、
差分应用/合法范围及第一个完成重放的真实投递已核。当前全已见32来源64任务TRAIN
重放未齐，不能报告候选成绩/接受或B2发布成功。
证据Run03_B2_teacher1_actual_fresh_proposal_and_first_native_delivery_20261021.json。
B2首遇/真实教师输入与提案检查点共302成员已于13:14:16双盘逐字节核验保全，
两archive均d1eb3e57c39adb0cecf17b274957b07dbe8aa20504cfd20e96a6cda2be276680，
设备64528/64517；前后371主源/381接续pins保持。未把活跃progress或账本打进归档。
收据Run03_B2_complete160_actual_teacher64_checkpoint_preservation_20261021.json。

13:30额外核B2已完成首遇的真实推理预算，不增加生成：32组成对实际请求除messages
外全部字段一致，输出上限8192不变。按各角色32个唯一原始响应计，空库203883输入/
74438输出，技能212966输入/79593输出；实际多9083输入/5155输出，输出+6.92523%。
这些是分角色对照核算，联合真实来源仍只有60，4个完全相同请求共享，不能将两组
token相加当联合实际支出；同预算上限不等于同实际计算量。按原生分和真实开销
共同报告，不据此断言收益的唯一来源。成本证据并入13:30实际小时快照。

独立IID128 TEST和官方HF TEST语义/预测/评分仍未打开。最终方法、可信经验/静态
对照、三次学习、两机制消融、真实末库矩阵和统计实现固定后才统一评测。
分析计划research/OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md，主要EC/EV与最低
八比较族不变，完整EC/EV与负资产误引只作已声明描述性审计，不挑有利主指标。
来源cluster区间以实际库和固定解码为条件，不保证算法总体稳定或跨模型/新法域。
SkillCommit已有标签辅助修复/源重放，不能当原创或拿不同配置裸分宣布SOTA。

直接下一步：跟本Run B1全部首遇→实际教师CRUD/新反馈→发布，再重点核B2以后
相对强空库和自身B1的前向收益、完整输出/损害/成本；不反复B1资格测试。
当前具体动作：跟9771的B2候选1完整TRAIN决策→自然教师2→最终发布，不在部分
分数上手改库或重启B1。若观察器到期而原PID仍在，重新观察同一训练，不重启。
B2相对强空库有新案净益，但在线本来就等于固定B1，不据这个零点差停止；B3起
才看B2更新相对固定B1的收益。EV剩余(d)(5)遗漏已被教师自然修订明确涉及，需
以真实重放/准入与后续新案检验，不能把文字修改等同于行为已经纠正。
等待期间不为了填满工作时间继续增加通用检查或修改已冻结方法。
自身EC预测给EV的假设早在10/20只读分析中出现，当前48源正法条集合一致但题面
非字节一致；尚无干预。不得把它当新发现、偷偷用Gold start3或直接替换当前任务。

最近小时计划13:30、实际13:30:37.166062，延后37秒，下一14:30 Asia/Shanghai。
每小时按生效补充的五项核方向/技能/证据缺口/局部循环/下一动作，不把token当时间。
13:30主/静态/接续371/117/381绑定及50packages不变，真实三个原进程句柄仍在；
账本354预约/天花板1797，旧350前缀未改，ACE目标仍未freeze或训练。本轮主要是
同句柄verified wait，另完成已落盘B2真实预算/成本核算，不冒充新的性能实验。
证据hourly1330_Run03_B2_C1_alive_actual_inference_budget_and_cost_20261021.json。
该小时快照/成本重算程序、当前索引及上一B2完整检查点收据共3成员已双盘保全，
两archive均85128affe27718f41616496b7144ebcd31dc3dedb6da28754e8df34d94ab5374。
收据hourly1330_actual_inference_cost_checkpoint_preservation_20261021.json。
后台systemd不依赖对话在线，观察器不是独立唤醒调度产品。Goal继续active，未完成。
上一Goal续接为progress：实际完成B1发布/自己的B1快照、完整成本和706成员保全。
本次为progress：核实完整B2新案净益和实际64任务教师反馈，跟到自然5项CRUD
及第一条真实提案投递；非新增资格测试。同一进程的持续轮询另计verified wait，
不是新性能实验或阻塞。第一检查点456成员、第二222成员及B1终态706成员均双盘
逐字节保全。未实施EV作者契约修订，未改冻结学习/执行源。
B1最终发布及B2完整首遇已完成，B2最终发布未完成；成熟对照、三重复、消融和
隔离TEST仍未完成，完整论文目标不缩减。

旧索引完整归档：research/CURRENT_GOAL_HISTORICAL_Run02_through_20261021_1007.md；
更早1204行与9月27日起可追溯记录按旧归档链保留，不把历史游标当当前状态。
