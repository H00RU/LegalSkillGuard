# Current legal skill-evolution goal

更新：2026-10-24 00:07 CST。此页是当前入口；进程状态以实际systemd和原始制品为准。
旧11:46入口逐字存于[恢复前快照](research/checkpoints/CURRENT_GOAL_before_teacher_timeout_recovery_20261023_1440.md)。
旧ACE Run03、旧静态/Text等待器及旧只读观察器已失败，不可当作仍在运行。
当前静态Run03已自然成功完成，不与旧失败运行混淆；Text45现已实际开始。

## 本次Goal执行更新：先完成论文证据，不重开方法探索

原生Goal仍为active，研究目标不变；以下是当前执行优先级，不是新开或重置Goal。
用户要求保持思路、推进论文并判断指标合理性，不能用反复工程检查代替实验完成。

1. 保留已有八批主方法及全部正负证据，完成Text45、两项45消融、六个145/245独立
   构建，再统一冻结16臂测试。当前不得因对照耗时长而减样本、减重复或换法律任务。
2. 只为尚未开始的145/245构建准备共同执行提速；45两项消融继续原环境，匹配main45。
   接续工作聚焦精确源码兼容、一次有限交接和实测吞吐，不再增加资格测试框架。
   现有Text、等待器和单模型保持原样；提案在发布与边界核验前仍未部署。
3. 论文v0.13的已核实文字、图和数值不因进度计数反复重写。优先补齐真实实验缺口；
   新完成结果再进入对应结果段，不能把TRAIN曲线填入正式TEST主表或编造显著性。
4. 指标判断使用完整来源、同案同阶段对照、原生未舍入F1及无效输出原分；不强求
   不同案件批次机械单调。需同时看强空库、实际自身B1、成熟方法及两消融，记录
   逐案损害与技能真实发布/投递。三份学习库不是384个独立测试来源。
5. 重点核对已发现的边界：EC持续进化相对B1增益小于EV；EV金额错配没有随漏引减少
   而全面改善；静态库不是必然强于空库；ACE外包装不同，不能作纯更新规则的因果结论。
   后续结果不理想时先定位全样本实际失误，不隐去不利对照、挑库或回填旧好成绩。

23:28原始进度：Text45已112/256源预测、第4批、0教师，尚未进入技能构建；
没有新的Text技能或成绩。四个原systemd单元均active、PID未变，A40利用率97%。
论文当前已完成证据仍为完整TRAIN：主方法82.03/79.16、强空库60.17/62.92、
ACE适配61.87/53.85、盲静态61.73/62.38（EC/EV F1百分比）；不是正式测试成绩。
本次小节是执行交接记录，后续以新实际制品更新，不把过时快照当实时状态。

23:42用户补充：EC相对自身B1的后续增益值得优化，允许按证据自主安排，
也允许当前方法够用时先完成冻结测试，不要求立即推翻主方法或重训所有基线。
已向用户澄清静态于20:59完成，现在是Text45，23:41为124/256源预测、0教师。
当前选择是先保留原主方法完成Text与两项消融，利用它们判断EC的实际瓶颈，
不要在成熟对照未齐时另开主训练；若完整证据足够，继续既定重复及统一测试。
若需优化，用TRAIN历史和消融定位并显式开新方法版本，旧八批及对照失败全部保留。
Text末库TRAIN应对主末库完整重放86.03/89.30，不对冷启动在线首答82.03/79.16。
任务、执行器与协议不变时，已学得ACE/Text/静态库可以复用，无须因主方法修改一概
重训；若这些共同条件改变则重新判断可比性。正式TEST不作反复调参选版工具，
开封后据其结果优化的新版本不自动继承“同一测试独立盲测”的证据资格。

## 目标、用户澄清与研究主线

以冻结Qwen3-8B证明可进化技能在后续新案和隔离测试上，相对同工具权限、同单答预算
的强空库及可信经验方法有可复核净收益；完成必要消融、独立学习重复和完整论文。
当前保留OpenExempt EC/EV，不因单批裸分或对照期间没有刷新主成绩而另换路线。

用户已明确：现有主方法完整八批有足够正向证据，正因此进入对比和论文写作。
优先保留这版方法完成实验。教师交付候选不自动采用；若成熟TRAIN对照暴露实质
不足，再有意识地决定新版本及匹配重训。不得把“没有新增主训练”说成“既有收益失效”。

师兄paper-experiments-appendix为实验组织主参考：研究问题、对照、机制、成本和
可支持结论对应。引用和实际代码来源如实保留，不虚构模板中的五次重复或三个创新点。
正式性能主表使用独立测试；现有八批曲线和同案首次遇案对照属于TRAIN过程证据，
足以支持继续完整实验，不代替冻结测试、独立重复或显著性结论。

不新增付费服务、第二实例、32B、fallback、答案修复、隐藏求解器或无关框架。
不挑案、改评分、删失败、选旧好库或虚构单调曲线。不用验证集；已见TRAIN重放
是优化。所有原始失败与实际成本保留，源码和制品双盘备份。封存TEST题面、标签、
预测和成绩仍未读取；不得以测试反馈优化方法。

## 已完成主方法与完整八批首答

项目：`/media/sangfor/vdb/legal-skill-evolve`；
用户入口：`/home/yndx/hhy/legal-skill-current`。

主Run：`legal_openexempt_closed_feedback_public_assets128_20261021_run03`，
10月22日12:09:47自然完成128来源、8×16案、每案EC/EV两个任务和8次唯一发布。
方法source6896246；四个实际主actor/scorer文件仍匹配原冻结字节。
这是标签辅助外部技能学习，不更新8B参数，不是无标签TFGRPO。

每批用批前实际发布的库首答，所有条件完成后才释放本批训练答案。
批后重放不覆盖首答。完整128来源/每方法256任务的首次遇案均分：

| 条件 | EC F1 % | EV F1 % |
|---|---:|---:|
| 强直接空库 | 60.17 | 62.92 |
| 主方法在线库 | 82.03 | 79.16 |
| ACE原生角色任务适配 | 61.87 | 53.85 |
| 盲法条固定库 | 61.73 | 62.38 |

主方法相对空库+21.86/+16.24pp，相对ACE适配+20.16/+25.31pp。
完整静态TRAIN于20:59完成；主方法首答相对它+20.30/+16.78pp，B2–B8每批两端点
均高于固定库。固定库相对空库+1.56/−0.54pp，只是描述性差异，不作等效性检验。
这是单seed45 TRAIN学习流。ACE冷起步提示/外包装也不同，不能把全部差距归因于
技能更新规则，或称已超过作者原生实现及官方TEST SOTA。所有ACE无效输出保留零分。

| 批次 | 强空库EC/EV % | 主方法EC/EV % | 批后记录/tokens |
|---|---:|---:|---:|
| B1 | 63.45/66.35 | 63.45/66.35 | 5/1591 |
| B2 | 68.71/64.51 | 83.68/74.45 | 6/1945 |
| B3 | 64.70/60.79 | 91.42/82.42 | 6/1945，NOOP |
| B4 | 54.95/57.17 | 83.85/79.84 | 6/2179 |
| B5 | 55.97/65.31 | 86.77/80.83 | 6/2182 |
| B6 | 56.31/67.72 | 84.60/83.44 | 6/2202 |
| B7 | 58.13/61.56 | 78.55/80.76 | 6/2223 |
| B8 | 59.12/59.96 | 83.90/85.21 | 7/2486 |

自身B1库冻结对照：B2–B8全112案，EC+0.85565/EV+9.39396pp；
B3–B8全96案，EC+0.99826/EV+10.95961pp。EV持续收益明显，EC增量较小：
96案中80个EC指导/请求未改变；EV有75个改变。不是只挑改变子组计主指标。

主末库7条/2486tokens，SHA
`3387b5b450f4b9107c9738562fa224915bb4405ff329ca8f113fc05d0e9c76e7`。
实际7CREATE、14UPDATE、0DELETE/MERGE；支持接口不等于实际发生。
完整成本1158次8B生成，7655443输入/3232344输出，全stop；
15教师响应，3232522输入/51361输出，含35912推理tokens，不重复相加。
另81次生成到终态仅供B1冻结库评测，不能从总成本中隐去。

[完整128首答汇总](../artifacts/research/openexempt_legal_scope_20261020/Run03_vs_ACEv4_complete_B1_B8_equal128_prequential_FIRSTS_ONLY_last_learning_cost_pending_NOT_TEST_20261023.json)。
其余机制/内容/残余审计见[证据索引](../paper/evidence_and_completion_20261020.md)及上述历史快照。
当前独立教师交付候选6cbc2c9仍未采用，不与现行主方法结果混用。

下午补齐的14候选机制核对显示：9次实际接收中，4次库结构不同于只按EC/EV任务
选择的组合；B1C2保留了任务级EV门槛未过的IL分量。三个已见TRAIN来源原EV
F1从57.41%到79.63%，只作局部机制例证，不是新训练主指标、独立消融或TEST。
[结果段及限制](../paper/method_scope_and_failure_decisions_20261021.md)与
[完整14候选](../artifacts/research/openexempt_legal_scope_20261020/Run03_all14_actual_component_vs_task_gate_decisions_and_B1C2_Illinois_EV_rescue_NOT_independent_ablation_20261023.json)
保留全部拒收，不额外开启任务级学习或扩大16条件矩阵。

## 当前进程及断点恢复

唯一模型：`legal-qwen3-8b.service`，PID3613253/start446037091，engine3613750。
bf16 Qwen3-8B revision b968826d9c46dd6066d109eabc6255188de91218，
vLLM0.10.2/xgrammar0.1.23，32768/8192，thinking开，T0.6/P0.95/K20，
serverseed42，maxseq1，prefixcache关。无模型替换、重启或第二实例。

17:25本机健康误报已核清：当前工具终端有HTTP代理，普通curl到127.0.0.1会经
代理返回502；显式`--noproxy 127.0.0.1,localhost`直连返回200。训练使用的既有
`openai_client.py`已经通过`ProxyHandler({})`禁用环境代理，其readiness也为真。
原服务/引擎PID未变，静态预测继续增加。同类NCCL TCPStore监控告警最早在
10月20日17:45已出现，不能仅见这条W级日志便认定模型刚退出。没有重启、停止
训练或修改客户端；原store断连的具体原因未据此证实，也不把告警解释成指标原因。
[实际直连/代理/readiness与原PID进展记录](../artifacts/research/openexempt_legal_scope_20261020/static03_old_NCCL_warning_shell_proxy_health_false_alarm_actual_same_PID_readiness_forward_progress_20261023.json)。

ACE旧Run03在10月23日13:28:26停止：b8_295_EV_r1_reflector超过原600秒。
旧异常分支未保存stdout，不能证明是capacity、网络或远端推理问题，失败usage未知，
不是零。850native/373教师响应/374attempts和3550成员终态两份档均保留。
全部八批首答已完成，之后的学习超时不会改变这些原始分数。

已完成的ACE45接续Run：`legal_openexempt_ace_public_assets128_20261023_run04`，
unit `legal-openexempt-ace-public-assets128-20261023-run04.service`，
前PID2150612/start474251167，14:13:14启动、15:48:37自然结束；source048b021，383绑定文件/50packages。
同一学习器接续，不是新独立重复。恢复唯一B7末库20条/2059tokens，SHA
`f609fbcc16f9d9015f98adf46d39af863ef784328fc44d21d9639562e5ea8f94`；
恢复845原始生成、366教师响应及全部96逻辑B8首答。首答逐项原路径/答案/分数相同，
没有新首答生成。现已自然完成896native/423成功教师/423attempts（含恢复前缀），末库21条/2158tokens，SHA
`75ad535aed4478ce4c85832138dadcb3dc460fec8200704151a002920131af56`。
计入旧B3与本次旧B8退役工作，总911次8B生成、442成功教师/443attempts；一次超时usage未知，
不能按零计。[实际完整成本](../artifacts/research/openexempt_legal_scope_20261020/ACEv4_Run04_complete128_terminal_actual_retained_and_retired_B3_B8_cost_NOT_TEST_20261023.json)。
B8全部32条TRAIN反思/标签/计数/ADD已核，完全正确从5到25是同案拟合，不是新案收益。
旧20条正文保留，新一条为复合资产中心名词/修饰词的类别判定程序；未在更晚TRAIN验证。

本次退役B8未提交学习5native、7教师成功响应、1失败attempt，8attempts保留。
此前退役B3的10native/12教师另外保留，不能漏掉、重复计入或导入恢复库。
教师模型gpt-5.6-sol/high、600秒、capacity-only no-result retry和学习算法均未改变。
只修超时后stdout/事件日志保留，以及严格的同版本已提交前缀恢复。
[协议](research/OPENEXEMPT_ACE_TEACHER_TIMEOUT_CONTINUATION_20261023.md)。

## 已实际挂上的自动接续

所有stage保持单实例、规范独占训练锁、新Run ID、失败即停，不按成绩选库或自动重试。
“active”等待器不自动代表已学习。ACE与静态均已完成，Text45已从等待转入真实源轨迹生成：

- 静态TRAIN：`legal-openexempt-fixed-static-train128-20261023-run03.service`，
  前PID2155494/start474269030，于20:59:00自然完成，现inactive/success。
  固定原7条/2411token库始终不变，全128案256预测先于评分，0新教师、256stop、0格式错。
- Text45：`legal-openexempt-static03-to-text45-20261023.service`，
  PID2156118/start474271148。静态自然结束和双盘核验后，已按原计划把共享上限3349扩为
  3991，于20:59:19实际初始化seed45 run02；21:12快照为9/256源首答、0教师。
  先独立完成全部256首答再释放标签，之后256轨迹分析+64合并+1翻译，不导入其他方法答案。
- 剩余八stage现由`legal-openexempt-text45-legacy45-phase-repeats-20261024-run02.service`
  接续，PID3019419/start477802191，于00:05:04启动，仍只等上述Text，未启动子学习。
  原等待器2183806已核实无子进程、无阶段/扩额后于00:03安全退役，Text和模型未停。
  新等待器先按原配置跑两项45消融，再在明确边界统一准备六个145/245新版本。
  下表是完整保留的原阶段/额度计划；后六项run02不会被覆盖或再启动，边界后才
  根据实际新环境生成run03，保留原方法、数据、预算及原始配置：

Text另有仅归档的有限观察器`legal-openexempt-text45-milestone-preservation-20261023.service`，
PID2815942/start476967418，于21:45:56实际初始化。它绑定原Text与模型PID，仅在完整
256源轨迹封存和最终技能发布两个不可变阶段各做一次双盘逐成员hash归档，随后退出；
不评分、不读TEST、不调用模型/教师、不改训练或队列，也不重启任何进程。
脚本与阶段记录位于`artifacts/launches/openexempt_text45_milestone_preservation_20261023`及同名`.py`。
21:43首批32条原生源作答已齐，均stop、无解析错、空技能输入；这不是学习效果或全量完成。

| 顺序 | 方法/seed | 新profile后缀 | 阶段结束前额度 |
|---|---|---|---:|
| 1 | whole-bank消融/45 | 20261023_run02 | 4023 |
| 2 | first-commit消融/45 | 20261023_run02 | 4055 |
| 3 | 主方法/145 | 20261023_run02 | 4087 |
| 4 | ACE/145 | 20261023_run02 | 5639 |
| 5 | 主方法/245 | 20261023_run02 | 5671 |
| 6 | ACE/245 | 20261023_run02 | 7223 |
| 7 | Text/145 | 20261023_run02 | 7865 |
| 8 | Text/245 | 20261023_run02 | 8507 |

3991是当前实际共享预约上限；表中后继值是已声明上限，不是实耗。每次扩额必须先验证前阶段
真实自然完成、两个独立盘终态archive hash、源文件与环境、全部历史预约不变。
新11份冻结均逐字匹配当前源码/50packages；旧manifest不覆盖。
[11配置核验](../artifacts/research/openexempt_legal_scope_20261020/timeout_recovery_all11_frozen_profiles_exact_algorithm_fields_and_source_bindings_QA_20261023.json)。

## 最终测试与论文

[当前16条件/12来源配置及十主要四次要比较交接](research/OPENEXEMPT_FINAL_MATRIX_CURRENT_LINEAGE_20261023.md)
已按实际源配置核对；不是可执行TEST配置，不代表未完成末库已经合格。

独立正式评价仍在隔离worktree
`.venv/evolution-control-20261020.qLon9T`。现已补齐嵌套B2/B7恢复链核验、
原B8零分保留和全部退役成本。教师日志修复所在共享文件不冒称字节未变：
保留原hash源码，除未用于最终推理的teacher_call与其新增subprocess导入外，
所有AST必须相同；任何native actor/scorer改动仍拒绝，原源码进入最终冻结。
实际4873路径/6项负面探针及评价CPU106项通过。ACE45完成后又按实际completion通过完整
嵌套来源检查，三份学习沿革终态档均核两盘hash；仅该来源合格，不代表16臂或未完成末库已合格。
[已完成ACE来源与末库核验](../artifacts/research/openexempt_legal_scope_20261020/ACEv4_Run04_actual_complete_bank_nested_origin_final21_content_and_all3_terminal_archives_QA_NOT_TEST_20261023.json)。
[实际恢复链/actor核验](../artifacts/research/openexempt_legal_scope_20261020/ACEv4_Run04_actual_nested_B2_B7_B8_origin_and_main_native_actor_identity_CPU_QA_20261023.json)。

必须等待全部真实末库、三次学习重复、两项消融、16臂及原统计计划后冻结TEST矩阵。
128独立来源、EC/EV两端点；不是256或384独立案件。共同evaluation seed45，
三组实际学习库不冒充三个独立解码重复；条件source-paired bootstrap20k，
PCG64 seed2026102192，十项主比较、四项次比较。法域相对task-local贡献若无独立
消融，投稿前收窄原创主张；不以代码检查替代机制消融。

未来单实例4请求调度已实现但未部署；当前模型maxseq1不动。原最终评价协议要求全部
学习完成保全、恢复资产核验及新环境捕获后才切最终评价环境，不能热改训练服务。
23:55发布的[有限交接增补](research/OPENEXEMPT_PHASE_DISPATCH_HANDOFF_20261023.md)
前瞻性调整这一时间边界：Text45与两项原45消融全部自然完成保全后，才允许六项尚未
启动的145/245重复共同切新调度。未发生的交接不能冒称已经部署；不改原45冻结和运行。

论文工作稿v0.13和双语21页内部审阅PDF已完成：新增完整静态TRAIN行、实际收益与失误
清单、成本及Text45真实启动状态。摘要、引言、相关工作、数据、方法、原八批表、原首答
数值、两图及8条文献不改；只更新评价设计和5.4中已完成证据，正式待填保留。
347文本单元/6表/2原图，实际PDF文本差异0，已视觉检查1/12/13/20页。
[当前内部审阅PDF](../artifacts/research/manuscript_review_20261023/v013_bilingual_internal_v01/legal_skill_evolution_v013_bilingual_internal_review.pdf)
及[最终审阅QA](../artifacts/research/manuscript_review_20261023/v013_bilingual_internal_v01/final_review_QA_20261023.json)。
正式TEST主表、重复变异和消融结果仍待补，黄色待补不填0或TRAIN值；当前不是可投稿定稿。
旧v0.12精确源稿快照及21页PDF、v0.11及此前版本、两图均保留。README是活跃源码冻结快照，
不热改其绑定字节；运行和稿件当前状态以本页为入口。

续接核实：v0.12源码、PDF和ACE终态证据的31成员增量档已双盘逐成员核验，
见[双盘收据](../artifacts/research/openexempt_legal_scope_20261020/paper_v012_rootcd66bea_actual_ACE_terminal_scope_evidence_and_review_scoped_dual_preservation_20261023.json)。
静态完整256预测、原生请求、解析、固定bank hash及先存预测后评分均核清；原生EC/EV
为61.73%/62.38%。其两盘终态档各789成员逐项hash通过，不同device，全部失败保留规则不变。
实际成本256次8B/256HTTP，输入1836443、输出640206、0新教师，执行与评分约5h10m，
原静态编译另计。完整诊断中，静态→主方法首答EC漏引432→221、EV漏引390→209；
EV金额错配50→67，故收益不能写成数值执行全面改善。这些是主张出现次数，不是独立案件。
[实际全量结果/失误/成本/双盘与Text交接](../artifacts/research/openexempt_legal_scope_20261020/static03_complete128_256_predictions_actual_metrics_residuals_cost_dual_preservation_and_Text45_handoff_NOT_TEST_20261023.json)。
Text45及剩余八stage进程实际存活；8B仍原PID3613253，未重启。当前证据支持保留现行
主方法，继续Text、两项消融、独立学习重复和最终隔离测试，不自动采用教师交付候选。

最近邻SkillCommit的论文、作者主页和公开仓库列表复核未找到已验证的作者实现
链接，范围及贡献限制已记入[方法边界](../paper/method_scope_and_failure_decisions_20261021.md)。
维持两个外部适配对照及当前16条件；不据未复现近邻的公开异协议成绩宣称胜出。

17:09已补齐师兄paper-related-method所需的十篇同行原文缓存和
[同行写法研究v1](../peer-papers/同行写法研究-v1-20261023.md)，逐篇核对摘要、引言
组织、方法与实验设置，注明阅读范围，不声称读完所有附录或复现十个方法。
[来源清单](../peer-papers/20261023-scope-consolidation/source_manifest.json)
记录实际版本/URL/全文hash、摘要逐句规则计数和功能标注、抽取重算程序；原文
缓存不提交到公开源码。该17:09研究聚焦最近邻归属、术语和实际对照覆盖，当时未修改
正文/附录D、v0.12 PDF、原图、方法配置、16条件或队列，0原生/教师/TEST调用。
最终写作仍等实际比较与TEST，不因同行模板另加多轮任务、验证集、模型或框架。

下一步：ACE与完整静态成绩、失误、成本及来源已核；Text45源轨迹生成已实际开始。
继续检查其实际技能内容/投递/拟合效果，依次完成既定独立重复、消融和冻结测试。
Text末库TRAIN拟合对照主方法实际末库128案重放，不与在线冷起步首答混比。
21:08方向复核：本轮新增的是完整静态对照及收益定位，支持保留方法，不增加调试支线。
遇到实质问题先看完整证据，
不把工程维护夸成性能突破，也不脱离现行主方法再次原地换任务。

## 23:08效率审计与隔离提速准备：尚未部署

用户指出ACE约24小时，实际完整沿革为23.5756h：911次8B生成相关文件区间18.7174h，
442成功教师调用3.6193h，其余1.2389h含中断/超时等未全部分解；不是GPU忙时积分。
GPU当时98%，慢的主要部分是原maxseq1下的大量长思考串行生成，不是CPU检查。
23:06快照Text已97/256源作答、第4批、0教师；当前Text、后继队列及原模型仍存活。

隔离worktree为`.venv/phase-dispatch-20261023.pvio7N`，分支
`prospective-phase-dispatch-20261023`，提交`0a73ed2496979d22ecb034329fbc14261956a9dc`，
基于本规范目录的bc7c203。已把独立阶段的有界保序并发接入主方法、ACE和Text，
保留原回答/评分/传输/准入及尾组规则12个AST；整条原生推理函数未改。
精确wire锁保证重复请求一个物理来源，进度和教师计数串行写，失败取消后续并保全在途。
ACE同案轮次及原row/round标签顺序不变，Text同层合并后仍有层间屏障。
36项聚焦CPU检查0.42s通过；连同既有ACE/Text契约78项3.29s通过，17个原评分器空切片
warning保留。没有模型/教师/TEST调用，也尚未实测GPU吞吐或部署新服务。
[来源/CPU/实际进程审计](../artifacts/research/openexempt_legal_scope_20261020/phase_dispatch_prospective0a73ed2_critical_path_source_AST_CPU_and_live_unchanged_NOT_DEPLOYED_20261023.json)。

拟定边界是保留当前Text45及两项seed45消融的原运行配置，匹配现有main45；然后只给
尚未启动的六个145/245构建统一新执行版本，按seed匹配三种方法。原16臂、十主要四次要
比较、三个实际学习库、预算、标签时序和旧成绩均保留，不新增一次主45或挑旧好库。
必须披露45与145/245的执行配置差异，不能把变异冒称同一调度下的纯seed方差。
[隔离提案及待完成边界](../.venv/phase-dispatch-20261023.pvio7N/docs/research/OPENEXEMPT_PROSPECTIVE_PHASE_DISPATCH_20261023.md)。

当前8stage控制器仍是原PID2183806，尚未替换。下一步先完成v1/v2原始源码保全与正式
评价器来源兼容、实际新环境/六配置冻结及精确交接；新协议发布和原45阶段保全前，
不改变有效部署边界，不停活动学习，不热改冻结源文件或服务。GPU检查仅允许边界后
8次固定公开TRAIN传输/计时请求，不读标签、不评分、不取代后续学习或正式TEST。

23:37续接已完成隔离版来源兼容：复用正式评价器f138而非旧canonical入口，保留
16臂、完整学习链、实际失败和原统计门槛。五份完整历史源码均保存精确hash；仅允许
已核实的四个执行文件版本差异，新五文件bundle逐字绑定，actor/grader/准入函数
另核AST，其他评分/传输/数据文件不豁免。显式最终调度声明、原45串行源码、
145/245实际init/completion收据及各方法同seed环境均须一致。
既有正式评价检查、调度和ACE/Text契约合计206项25.16s通过，17个原空切片warning保留；
未调模型/教师、未读实际案件包或TEST，也未部署。来源兼容准备不代表尚未构建的
全矩阵已经通过。Text进度121/256仍为源轨迹，0教师；无新技能或成绩。
[论文证据与合理性执行清单](../paper/evidence_and_completion_20261020.md)已补齐，
v0.13正文/附录D字节不变。剩余工作聚焦实际部署边界和完成实验，不再扩展测试支线。

## 00:07有限后台交接已实际排队，推理提速尚未发生

实际脚本是`artifacts/launches/openexempt_text45_legacy_ablations_then_phase_repeats_20261024_run02.py`。
新队列31个源/配置/五份历史源码成员已两盘逐成员保全，queued记录、两盘archive SHA
均已核验；实际PID3019419仍活着。模型PID3613253、Text2156118与归档观察器
2815942保持，当前共享上限3991、865个原预约不变。Text第5批149/256、0教师，
A40利用率97%、显存34675MiB；不是新增技能、学习收益或推理加速成绩。

新执行文档和未注册的四序列单实例unit已提交9333e76，但当前模型maxseq1未动。
有限控制器复用原八stage/终态/额度检查，只在Text和两项45消融自然完成、双盘保全、
原部署/恢复资产复核和独占训练锁后，提升已审查提交0a73ed2及8337a1d，停止旧服务
再启动同权重四序列单实例，捕获真实环境、做八次不评分TRAIN计时，再冻结六个新profile。
全部16臂、三个学习seed、十主要四次要比较不变；此控制器从不打开TEST或选库。

首次交接启动仅在归档时失败：函数参数stage被枚举配置的循环变量覆盖，导致归档
文件名成为字典；未产生学习子进程、额度扩展或源码/模型切换。旧源文件/失败JSON
与修正新版本均两盘保全，不覆盖历史。修正名为archive_label，并用枚举全部阶段的
CPU契约确认不会再覆盖；六配置语义逐字投影、ACE/Text原校验及生成freeze代码编译
均通过，不新增资格循环。手工第一次备份检查把收据新增at时间当作预算变化；随后
逐键证实全部实际预算键及865预约相同，只排除收据包装at，没有放宽历史检查。
[失败根因与保全](../artifacts/research/openexempt_legal_scope_20261020/finite_phase_handoff_bootstrap_failure_root_cause_corrected_version_and_dual_preservation_20261024.json)。

小时方向复核：当前方法已有完整TRAIN净收益，主要缺口是成熟对照、重复、消融和
正式TEST，不能再只优化启动工程。有限交接就绪后不再加调度框架；下一步跟踪Text
实际技能内容/投递和完整拟合，结合两消融决定EC是否需要新方法版本。
当前不动主方法、不采纳6cbc候选，不把金额错配或EC持续小增益藏掉；不据TEST调参。
