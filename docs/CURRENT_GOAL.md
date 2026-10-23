# Current legal skill-evolution goal

更新：2026-10-23 17:10 CST。此页是当前入口；进程状态以实际systemd和原始制品为准。
旧11:46入口逐字存于[恢复前快照](research/checkpoints/CURRENT_GOAL_before_teacher_timeout_recovery_20261023_1440.md)。
旧Run03、旧静态/Text等待器及旧只读观察器已失败，不可当作仍在运行。

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

主方法相对空库+21.86/+16.24pp，相对ACE适配+20.16/+25.31pp。
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
“active”等待器不是已开始学习。ACE已完成；静态03于15:49:13实际初始化，Text45仍等待静态：

- 静态TRAIN：`legal-openexempt-fixed-static-train128-20261023-run03.service`，
  PID2155494/start474269030。已接续执行固定原7条/2411token库，0教师，
  全128案256预测先于评分，0新教师。
- Text45：`legal-openexempt-static03-to-text45-20261023.service`，
  PID2156118/start474271148。等静态03自然完成且双盘保存，再把共享额度3349扩为
  原计划3991并启动Text seed45 run02。256轨迹分析+64合并+1翻译，不导入其他方法答案。
- 剩余八stage：`legal-openexempt-text45-to-remaining8-20261023.service`，
  PID2183806/start474380328。当前只等上述Text进程，尚无后续训练或额度扩展。
  一次性执行已声明计划，不是新通用队列框架：

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

3349仍是当前真实额度；表中是已声明的上限，不是实耗。每次扩额必须先验证前阶段
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

未来单实例4请求调度已实现但未部署；当前模型maxseq1不动。只有全部学习完成保全、
恢复资产核验及新环境捕获后才可按原协议切最终评价环境，不能热改正在训练的服务。

论文工作稿v0.12和双语21页内部审阅PDF已完成：补齐ACE实际末库/退役成本及细于任务拆分
的机制证据。摘要、引言、相关工作、数据、方法、原八批表、完整首答表数值及8条文献不改。
339文本单元/6表/2原图，实际PDF文本差异0，已视觉检查1/11/12/20页。
[当前内部审阅PDF](../artifacts/research/manuscript_review_20261023/v012_bilingual_internal_v01/legal_skill_evolution_v012_bilingual_internal_review.pdf)
及[最终审阅QA](../artifacts/research/manuscript_review_20261023/v012_bilingual_internal_v01/final_review_QA_20261023.json)。
正式TEST主表、重复变异和消融结果仍待补，黄色待补不填0或TRAIN值；当前不是可投稿定稿。
旧v0.11源稿快照与20页PDF、此前版本及两图均保留。README是活跃源码冻结快照，
不热改其绑定字节；运行和稿件当前状态以本页为入口。

续接核实：v0.12源码、PDF和ACE终态证据的31成员增量档已双盘逐成员核验，
见[双盘收据](../artifacts/research/openexempt_legal_scope_20261020/paper_v012_rootcd66bea_actual_ACE_terminal_scope_evidence_and_review_scoped_dual_preservation_20261023.json)。
17:08静态03仍为原PID2155494，进入B3，完成68/256原生请求、0教师，尚未评分。
完整前两批64预测已保存；当前全部68回答均stop、无格式错误或运行失败。
完整B1的32个实际HTTP请求已核：与主方法对应空库的题面、法条、公开映射、schema
和采样相同，区别仅为原零案件静态库文本；32个全部stop，无数值程序/解释器。
这是前缀执行核对，不是性能成绩或全128案完成。Text45及剩余八stage等待器
仍实际存活，Text未初始化；8B仍原PID3613253，未重启。

最近邻SkillCommit的论文、作者主页和公开仓库列表复核未找到已验证的作者实现
链接，范围及贡献限制已记入[方法边界](../paper/method_scope_and_failure_decisions_20261021.md)。
维持两个外部适配对照及当前16条件；不据未复现近邻的公开异协议成绩宣称胜出。

17:09已补齐师兄paper-related-method所需的十篇同行原文缓存和
[同行写法研究v1](../peer-papers/同行写法研究-v1-20261023.md)，逐篇核对摘要、引言
组织、方法与实验设置，注明阅读范围，不声称读完所有附录或复现十个方法。
[来源清单](../peer-papers/20261023-scope-consolidation/source_manifest.json)
记录实际版本/URL/全文hash、摘要逐句规则计数和功能标注、抽取重算程序；原文
缓存不提交到公开源码。新增建议聚焦最近邻归属、术语和实际对照覆盖，未修改
正文/附录D、v0.12 PDF、原图、方法配置、16条件或队列，0原生/教师/TEST调用。
最终写作仍等实际比较与TEST，不因同行模板另加多轮任务、验证集、模型或框架。

下一步：ACE实际B8发布、完整成本及来源核对已完成；等待静态完整256预测后解读
全部成绩和损害，再接续Text并检查实际技能内容/投递/效果，依次完成既定重复、
消融和冻结测试。遇到实质问题先看完整证据，
不把工程维护夸成性能突破，也不脱离现行主方法再次原地换任务。
