# 当前Goal执行索引

2026-10-22 20:09 Asia/Shanghai。Goal仍active，完整论文目标未完成。
Run03已于12:09完整结束八批128来源/256任务，八次唯一最终发布齐全；
旧ACE run01因重复技能ID被额外判为法律题零分，已于16:02:55安全停止，禁止恢复或
充当公平正式对照。修正v3已于16:14:04以新Run ID从空库正式启动；主方法不变、不重跑。
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

**19:11用户澄清后的执行责任**：最终交付是实验与论据支撑的完整论文，不是只监控
训练、汇报清单或等用户逐项挑方法。师兄paper-writing负责论文主线和成稿组织，
paper-ideation负责问题/贡献与近邻的接缝，paper-experiments-appendix负责实验矩阵，
由本代理实际选择、实现并执行必要对比/消融、整理图表与成本、完成写作核对。
这些skill不是仅供最后润色。模板中的固定三个创新、五RQ/五次重复、广泛迁移或
隐藏借鉴不能替代真实实现与证据；不为凑模板造理论、改弱对照或强求正结果。
现有主训练与ACE协议不因这次责任澄清热改，论文与实验可并行推进。

| 论文要回答的问题 | 对应实验和证据 | 当前执行责任 |
|---|---|---|
| 学得技能是否让冻结8B在未见来源变强 | 同案强空库、盲静态、外部经验方法与最终隔离TEST | 继续完成ACE；由本代理核对并决定必要的补充外部方法，首次TEST前冻结全部比较，不把只有ACE的最低矩阵自动等同充分覆盖 |
| 后续进化是否超过初次学得的技能 | 完整八批首遇及每次学习自己的B1冻结控制，三次独立学习 | 不只盯B1/B2；执行既定完整重复，分别报告EC/EV收益与损害，不要求换案裸分机械单调 |
| 当前两项设计为什么有用 | whole_bank及first_commit从空库独立学满八批 | 在当前ACE自然终态及保全后按既定顺序实际运行，披露单seed与计算混杂，不把日志回放冒充消融 |
| 技能实际如何生成、管理、使用，代价是什么 | 原始教师/发布/投递、实际CRUD、错误和调用成本 | 利用已有完整轨迹写机制与案例；如实区分送达、自报、关联与因果，不仅报告库条数 |

上述问题对应现稿三个RQ，不另造新任务/验证集/模型或第五套调度框架。
方法、数据、已完成TRAIN及局限可先写；TEST、重复和消融结果实际齐备后再补结果，
不能用“结果仍待完成”作为长期只审计不执行的理由，也不能提前把占位符写成胜出。

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
- 正在训练ACE v3：`legal_openexempt_ace_public_assets128_20261022_run02`。
  unit：`legal-openexempt-ace-public-assets128-20261022-run02.service`；
  PID176852/start466336240，16:14:04 CST直接启动，不是旧1738522或续接旧库。
  source commit `907d90e`；377文件/50packages在新性能前冻结。
  B1完整首答已于17:30齐全并独立核验，ACE EC/EV59.53125/55.29514%，
  同案直接空库63.44990/66.35417%；进入库0技能，不是成熟学习对照。
  64原始首答生成全stop、零解析/截断。18:45:04实际完成B1全部32条TRAIN和唯一发布：
  10条/1024tokens，book SHA `cbb3a75522b1f02ccf795d960aef3c4eaa625581736a1202e38659651867b317`。
  完整B1成本113生成/113HTTP全stop、782657输入/268129输出；52新教师响应，
  含51同案反思及1批级curator。19:54 B2完整新案首答齐全并已独立核验：
  ACE EC/EV65.78621/62.65873%，同案强空库68.70536/64.51389%，
  本方法83.67684/74.44940%；64原始生成/64HTTP全部stop，零解析错。
  全32空库原始HTTP、响应及评分均与主Run相同；10条技能均完整投递并有原生自报。
  这是首批学习后的16来源新案，不是成熟全流或TEST优势；不同原生提示包装使
  ACE对直接空库差值不能全归因于技能内容。当前正在B2 TRAIN更新，尚未B2最终发布。
  实际初始化仅七个空标题，0法律先验/0数值程序，不导入旧回答/教师/库。
  v3保留原始重复ID列表和法律答案，反思只按不同ID各标记一次；无答案修复或fallback。
  新协议：`docs/research/OPENEXEMPT_ACE_PROVENANCE_V3_20261022.md`。
  ACE原生Generator/Reflector/ADD curator，最多3轮TRAIN反思；不是作者默认原样复现，
  也不是总训练计算量相等。共享执行器、输入、EC/EV契约与生成上限，消耗成本另报。
  新v3 seed145/245的正式后续候选为同日run03，均377文件冻结但未排队；
  早先run02只冻结、未运行，其首轮账本/配对元数据已由新run03更正，不覆盖旧清单。
  目前仅ACE45在跑，不擅自并发抢GPU。
- 旧ACE run01的1738522已退出，unit MainPID=0/failed/Restart=no，
  failure明确为`InterruptedError('Operator stop at artifact-safe boundary')`，不是模型退出。
  B2完整首答54.23859/63.06052%受额外元数据拒收影响，不能用来宣称胜ACE。
  未改变法律答案的离线诊断EC60.76637%、EV不变，也不是新的正式运行成绩。
  所有原始分数/177次8B/56教师保留；双盘actual-terminal各955成员已逐字核验。
  诊断：`ACE128_Run01_integrity_stop_duplicate_metadata_root_cause955_dual_terminal_and_unmodified_legal_answer_diagnostic_20261022.json`。
  **18:26–18:30事实更正**：旧B2实际教师只处理197–200共8次反思，12份初始/重答
  均无解析错；204/212尚未进入其教师，也没有B2 curator/最终发布。故已证实的是
  两个首答被误判零分，不是“旧B1库已被该错误污染”。从经严格核验的检查点续接
  是可考虑的替代方案；当时选择从空库同版本重跑是更保守的保真决定，确有重复成本，
  不是已证明唯一必要的修复。当前健康v3继续，不再为此重启，也不按成绩改选旧好库。
  更正证据`ACE128_restart_rationale_erratum_actual_old_B2_teacher197_200_no204212_or_curator_20261022.json`。
  不修改活跃377绑定的历史协议来隐去原表述，本段及该独立证据覆盖其因果措辞。
- canonical锁：`artifacts/openexempt_training.lock`。
- 当前只读观察session **70202**，19:58:32启动，目标唯一B2发布与全部32条TRAIN
  逐字匹配，期限10月23日01:58:32只结束观察，不结束训练。原模型/ACE句柄不变。
  28878已于19:54:24见完整B2的16来源/32任务/96角色首答退出0，不再轮询；
  CPU25270已完成独立原始审计退出0，不重复执行覆盖报告：
  `ACEv3_Run02_B2_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261022.json`。
  40557已于18:45:38看到唯一B1发布及32轨迹逐字匹配退出0；CPU1372与包装7673
  也已完成完整B1审计，不再轮询。18:55新观察核原模型/ACE句柄，B2已有18/96个
  逻辑回答文件，125生成/52教师，仍在首答阶段，没有新批教师反馈或性能结论。
  84986及包装7599已于17:30:08见完整16来源/32任务/96角色首答退出0，
  CPU71645已完成新B1原始审计，不能再轮询；这不是训练终止。
  22314/7517已于15:55看到旧B2完整首答退出0，CPU15398完成旧B2审计。
  旧67586/72443/7499/15458/31275/7463/74968/60541/7514也均完成，不能再轮询。
  7480曾仅终止只读包装，不是停训。
  目标/终态制品优先于进程缺失判断；
  仍须核PID/start ticks/argv，不能仅凭索引、锁、progress或观察超时判断停训。
  旧11058/34994/46189/61360/94323/85265/88537均已完成，不再轮询。
- 17:30已核新ACE176852/start466336240、原模型3613253、三份377文件/50packages
  与主方法四个共享actor/scorer原绑定；GPU 97%，新轮无failure。
  小时证据`hourly1730_ACEv3_Run02_actual_new_handles377_original_model_and_direction_review_20261022.json`。
  该报告的84986字段指已完成的首答观察；40557及当时B2观察28878也已完成，
  现时B2发布观察为70202。
  18:30再次核同三份377文件/50packages、原PID/start/argv、依赖和主四共享文件，
  该小时教师阶段GPU 0%，不是服务退出；新证据
  `hourly1830_ACEv3_Run02_actual_new_handles377_original_model_and_direction_review_20261022.json`。
  19:32再次核同三份377文件/50packages、原PID/start/argv和主四共享文件，GPU96%，
  证据`hourly1930_ACEv3_Run02_actual_new_handles377_original_model_and_direction_review_20261022.json`。
  下一小时20:30 CST，不再要求旧ACE1738522存活。
  旧15:30小时报告为旧source修订前快照，不能复用其原样断言当当前状态。

## 冻结协议与保真

主方法执行/评分路径仍为`6896246`的原算法；当前ACE专属代码修订为`907d90e`。
主配置SHA `8c858d27892f278ee9cdd6c251486ce2080637aa5f01c51d165ecdab5fe2122e`；
主frozen371清单SHA `2cc50e6cfe05fb42c230aba570eb43e9fcd41c3287011f77de8291fd89418825`。
新ACE seed45 frozen377清单SHA
`964e4a6572a5b32221e69f73d439799fd11abdac3f0abf08f97b1d9102e24155`。
16:24实际新初始化、三份377绑定、原始生成prompt/schema不变、两处旧回答只移除
重复ID额外拒收的复核及旧56教师完整成本，见
`ACEv3_Run02_actual_fresh128_start377_source_raw_provenance_fix_and_old56_teacher_complete_cost_20261022.json`。
旧ACE56次新鲜教师输入1459325/输出39429，reason10323已含输出；响应2165.565秒
不是GPU小时。fresh response不等于供应商输入前缀缓存token为零。
新v3三份377绑定源码/配置、16:24成本与修正证据、旧失败及当前索引已作398成员
增量双盘保全，所有成员逐字核验、两档SHA相同：
`69ce562c7c1e232d47e400ffc52dda618e09a5555d14b54406693bfa5e6695c5`。
收据`ACEv3_Run02_new377_source_three_frozen_profiles_old_v2_failure_cost_and_current_goal_dual_preservation_20261022.json`，
也各自独立复制到两盘备份目录。不包含在写progress/部分首答，完整旧主源码/轨迹仍由
12:42联合档承接，不将本398成员增量档说成全部历史。
旧ACE382与主371的完整旧源码均已双盘保全；当前工作树不是与旧整份清单逐字一致。
修订只涉及ACE专属decoder/driver、对应小测试和NOTICE；四个共享直接actor/scorer
文件与主Run原绑定完全一致。不能把“主方法未变”误写为“旧371全源当前仍原样”。
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
vLLM0.10.2/xgrammar0.1.23/serverseed42/maxseq1/prefixcache关/KV5368709120。
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

下方标明旧ACE的B1/B2为已停止的v2开发记录，不进入正式对照或三次一致重复。
新v3已完整B1空playbook首答；学习后新案成绩仍待完成。旧B2较差受元数据适配器
额外零分影响，不能当作胜出。

新v3首批报告为
`ACEv3_Run02_B1_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261022.json`。
96逻辑记录的原始HTTP、schema、解码及评分逐项重算，64生成/64HTTP全stop，
421456输入/158202输出；32共用空库完整HTTP、实际内容与原分均匹配主Run。
原生ACE冷角色在32任务上4好14坏14平，均值−7.48884pp；这不是有技能的结果，
不据此热改角色包装或声称胜过成熟ACE。
首个来源181 EC的三次新教师均为实际gpt-5.6-sol/high、完整正确目标字面值、
无工具/响应复用，全部开始于本批完整首答落盘之后。三响应输入66817/输出2103，
reason536已含输出，前缀缓存11136已含输入，响应82.388秒不是GPU小时。
此为固定前三次教师的阶段成本，不是完整B1训练或实时总量，也不证明理解/泛化。
证据`ACEv3_Run02_B1_complete_first96_64raw_and_first181EC3_actual_teacher_label_evidence_20261022.json`。

旧v2 ACE B1完整首答报告：
`ACE128_B1_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261022.json`。
原生角色空playbook当前低于直接空库，32任务4好14坏14平；不是解析/截断或空库
请求变化，不热改作者角色或据初始空库判断最终效果。14:48实际教师/curator已完成，
须继续完整后续新案来判断学习效果。
首批固定成本64生成/64 HTTP、421456输入/158202输出，包含角色包装和直接空库，
不是已进行中的训练重答成本。181 EC的三次实际教师请求均核到完整正确标签字面值，
全新gpt-5.6-sol/high、无工具/缓存；三响应66467输入/2114输出，非当前教师总量。
小时证据`hourly1330_ACE128_complete_B1_first96_actual_teacher3_labels_and_original_service_bindings_20261022.json`。
GPU在13:29学生重答为96%，13:31教师阶段为0%；模型/ACE原句柄都在，不能把正常
教师阶段GPU闲置误判成模型服务退出。历史350预约前缀保持，369预约/3349为当时账本快照。

14:49已完成实际B1全32轨迹、所有教师与原始wire/解码/评分/原生ADD/计数语义审计。
47次反思请求均核到正确目标字面值，另1次为批级curator；共48新鲜响应，原首答不变。
109原始8B生成全stop/0传输错，752409输入/259556输出；教师1280162输入/33209输出，
reason8059已含输出，响应1940.342秒不是GPU小时。774tokens经原服务只读分词独立重算。
9条内容包括资产-条款穷举、独立通配、实质条款过滤、上限/共同债务人与类别事实边界；
code栏是文字核查模板，没有宿主解释器/求解器。发布确有可交付内容，不只是计数。
当批TRAIN完整声明误报/漏报均为零的任务由2变26，不是新案或TEST改善。
197 EC的B2真实HTTP中9条全文和hash均匹配，律师自报用了4条，未给本案反思或
未来/TEST反馈；自报使用不是因果效果，未读取或挑报部分B2成绩。
证据：`ACE128_B1_unique_actual_publication_all32_TRAIN_native_ADD_labels_tokens_and_cost_audit_20261022.json`、
`ACE128_B1_actual9_bullet_content_and_B2_first197_exact_wire_delivery_without_partial_scores_20261022.json`。
完整B1阶段696成员已于15:01在双物理盘逐字保全，包含109原始生成、48教师、
32 TRAIN、实际库和固定的首个B2投递证明，不含在写B2/进度/账本。两档SHA同为
`4c31291f9b3996398269efe7c3f53c447bb35c37064793d47817fdf61e539357`；
收据`ACE128_B1_actual_publication9_774_complete32TRAIN48teacher_and_B2_delivery_dual_preservation_20261022.json`。

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

## EC持续进化小幅收益的完整断点证据，18:30

不是仅看技能ID或技能总数：已从原始HTTP、实际公开任务/法域投影和原标签重建
全部128来源的256在线、256空库及224真实B1预测，共736逻辑任务记录；不是736
独立来源，也没有新增8B/教师/分词或TEST调用。B1未定义的控制不纳入增量计算。
B3–B8全部96来源中，EC仅16案的实际指导相对B1改变（14 OR、2 IL），10好3坏3平，
子组平均+5.98958pp；其余80案的完整HTTP、原始生成、答案和评分均与B1精确相同。
故整体仍只有+0.99826pp，不能将子组幅度替换完整分母或归因所有不涨于“律师不调用”。
EV有75/96案指导改变，45好8坏22平、该子组+14.02831pp，整体+10.95961pp。
这是同一学习库的描述性暴露分解，不是每句技能的随机化因果效果或独立TEST。
证据`Run03_complete128_first_forecast_actual_skill_projection_vs_own_B1_736_native_record_delivery_and_newcase_effect_decomposition_20261022.json`。

进一步按真实逐次父库重算全部15提案的分量门槛：B1后8份提案涉及11个改动的EC
连通分量，只有B2C2的OR和B7C2的IL获收；五个因本批或旧组原EC F1降低，另外
四个虽原分不降，却有完整输出或负资产误引损害。后者包含准入取舍，不证明未来
一定有害；也不能直接放宽规则美化学习曲线。保留预定whole_bank/first_commit独立
学习，先完成可信对照，不热改当前阈值、库或训练协议。
证据`Run03_all_postB1_EC11_changed_components8_proposals_actual_parent_scope_gate_failure_bottleneck_20261022.json`。

## 实际成本、双盘保全与下一步

17:06已将全部15次主教师、14个非NOOP候选和8次发布完整重建。实际9次接收、
5次拒收及1次明确NOOP；其中5次整份提案原门槛拒收，但公开法域/任务分量组合
获收。896项教师TRAIN目标条目精确核同（包含重复，不增独立n），每次最多32来源。
教师提案仅CREATE9/UPDATE24，实际创建7/更新14/删除0；没有观测到DELETE/MERGE，
不能以接口支持冒充实际管理效果。B3C2的NOOP确已进入发布，不是候选文件遗失。
这不是独立整库策略消融或新泛化结果。证据
`Run03_all15_teacher14_candidate8_publication_actual_scope_composition_and_library_management_accounting_20261022.json`。

完整主Run：1158原始生成/1158 HTTP，全stop；7655443输入/3232344输出tokens。
15次新鲜教师3232522输入/51361输出，reason35912已包含输出；
响应耗时1132.442秒不是GPU小时。包含全部失败候选，不含ACE/静态/早期研究/部署。
终态成本报告：`Run03_complete_B1_B8_actual_terminal1158_15_cost_20261022.json`。

14:23按1158个实际原始调用拆分耗时，八批依次约2:04、3:17、3:46、2:26、
2:21、5:55、3:49、2:38，并非逐批变慢。B1起点取首个native输入文件时间，
B2起取上一次真实发布时间；不假称已取到丢失的systemd启动时间。
各批首答/回放原始生成次数分别32/64、60/79、71/87、70/42、75/36、80/169、
78/104、84/27；总550/608。B6一次广泛提案即触发152次真实回放，EC/EV各76；
全批249次/731731输出tokens，B8为111次/324766输出tokens。
输入文件至原始回答落盘的区间合计占各批97.14%–99.19%，输出tokens/该区间
稳定34.63–34.76每秒；剩余可分解为教师响应和少量流程开销，没有发现小时级空等。
该文件时间诊断包含客户端检查、分词、HTTP、prefill、解码和写盘，不是核内GPU
解码速度、精确API延迟或GPU小时。总耗时约26小时16分；确实昂贵，不能用
“没有卡死”掩盖连续实验周转问题，但不在冻结ACE过程中删回放/改推理或调准入。
完整分解及文献边界保存在
`Run03_actual_eight_batch_runtime_decomposition_and_primary_OpenExempt_comparison_boundaries_20261022.json`。

同轮重读原始论文表格：
[SkillCommit v2](https://arxiv.org/html/2608.15165v2)表1中Qwen3.6-35B-A3B教师→
Qwen3.5-9B执行者的EC/EV macro-F1为：No Skill 15.61/9.97%、
ACE 34.57/26.31%、GSE 18.86/32.18%、SkillCommit 62.41/54.28%；
DeepSeek-V4-Flash教师/执行者的SkillCommit为96.01/94.28%。这是作者报告，
不是本项目复现，也不是已核验的全领域SOTA。其使用官方Advanced任务、每端点
210归纳/105测试、Qwen输出16384且thinking关；不能与本项目custom TRAIN
B8的83.90/85.21%直接排序。
[OpenExempt原论文](https://arxiv.org/html/2601.13183v1)表2/5中Advanced为6–8
资产、结婚比例1.0、5居所、干扰信息、全州且不给先前步骤答案；o3 EC/EV为
57.1/50.0%，GPT-5为55.4/49.6%。当前2–4资产、公开可用法域/start2更受控，
并非官方Advanced。公平有效性仍要靠本项目同配置成熟ACE/静态/独立学习和隔离
TEST，不能以跨配置高分宣称已胜近期工作。后续实验安排须同时考虑真实计算成本。

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

隔离最终评测工作树已同步v3两个ACE源文件及同名回归/NOTICE，commit b76187d；
增强的统计、静态控制和三次重复闸门及其测试与b50f24c逐字一致，没有整份覆盖为
根目录旧评测器。仅两项重复ID既有回归通过，0.28秒CPU，不做全量资格测试。
证明`ACEv3_Run02_isolated_final_eval_b76187d_two_provenance_regressions_and_enhanced_guards_preserved_20261022.json`
已独立复制到两盘；当前活跃377绑定均不变。

16:47后续六次完整128案学习配置已冻结和双盘逐成员保全，但均未启动/排队：
whole_bank/first_commit、主145/245各371文件，ACE145/245 run03各377文件，
均50packages。新ACE run03仅修正尚未启动配置的累计账本和同seed reference，
不改v3学习策略；实际全局账本仍3349、没有在此准备中扩额。
原主371当前仅ACE专属decoder与其测试两文件不同，其余369字节绑定仍一致；
新主重复不改原学习算法。实际参数通过隔离评测器三次重复/两消融闸门，但没有
伪造完成库或将13臂角色草案说成最终冻结TEST矩阵。
证据`remaining_six128_learners_frozen_real_repeat_policy_and_two_ablations_guard_no_launch_20261022.json`。
正式主/ACE种子45/145/245、两项单seed消融与全部末库仍须实际完成后才能打开TEST。

18:04论文初稿`paper/manuscript_v1_20261021.md`已更新至v0.3，补全真实标签辅助
连续反馈/部分接收方法、数据和执行参数、完整八批TRAIN表及真实7创建/14更新/
0删除合并和1158生成/15教师成本。两语言共用同一表，全部单元逐项核同实际
completion与不可变曲线；B2–B8对B1的0.85565/9.39396pp由未舍入值重算。
删除“主方法完成后等待启动ACE”的旧现时描述，保留所有TEST/重复/消融待完成项。
没有新增模型调用、测试框架、文献条目或学习代码，稿件不在活跃及六后续绑定内。
数值绑定证据`manuscript_v03_complete8_TRAIN_methods_actual_cost_and_pending_TEST_numeric_bindings_20261022.json`；
这完成的是可核查方法/描述性训练结果初稿，不是证明论文目标已达成。

新v3完整B1审计已完成：51个同案反思均核到正确目标字面值，另1个真实批级curator，
原生ADD及计数语义与唯一发布精确复现；原模型只读重分词独立得到1024tokens。
教师输入1373578/输出35215，reason7694已包含输出，响应1290.742秒不是GPU小时。
TRAIN完全正确任务2→25属于标签辅助拟合，不是新案/TEST收益。原B1首答不替换。
证据`ACEv3_Run02_B1_unique_actual_publication_all32_TRAIN_native_ADD_labels_tokens_and_cost_audit_20261022.json`。
已人工读全部10条实际中文技能，包含逐资产/法条穷举、专项与通用备选、先资格后
金额、共同所有权、实体法条过滤、类别事实与双向检查；code区为空，不执行宿主
程序，不手工补库，也不据文字内容断言法律正确或已产生效果。主库为英文，记录
这一实际产物差异，不热翻译或改变活跃原生角色。
首个197EC B2原始HTTP已核10条全文及hash，原生自报5个不同ID，未给本案TRAIN
反思或未来/TEST反馈；只证明投递/自报，不读取或挑报这个案的得分。
证据`ACEv3_Run02_B1_actual_bullet_content_and_B2_first197_exact_wire_delivery_without_partial_scores_20261022.json`。

完整B1及固定首个B2投递证据已完成720成员增量双盘保全，两盘逐成员及档案hash均一致：
`4424a028b782162087308a331bf0f99ce4a45fd286a8d3070b55919cb91b82af`。
收据`ACEv3_Run02_B1_actual10_1024_all32TRAIN113native52teacher_firstB2_delivery_and_current_goal_dual_preservation_20261022.json`。
这不是全项目源码档，也不纳入在写B2/progress/全局账本；完整源码由既有398成员及
主方法完整联合档承接。720档内的索引为当时快照，不声称包含后续19:09的本段修订。

## 外部方法与消融：19:09快照；19:48补充见下节

19:09时冻结最低矩阵中，**ACE是唯一外部自适应经验方法**；强空库、自身B1与盲法条
静态库是不同目的的控制，不是三个别人的方法。师兄paper-ideation用于机制接缝，
paper-experiments-appendix用于对照、公平性、重复和实际成本；方法名单仍须依据
原文与原代码判断，不是由skill自动选出，也不预设正文模板里的胜出/迁移/重复数。

额外方法的只读核对没有开启新实验。ExpeL固定作者提交
`e41ec9a24823e7b560c561ab191441b56d9bcefc`的实际代码保留规则与成功轨迹检索；
[原配置](https://github.com/LeapLabTHU/ExpeL/blob/e41ec9a24823e7b560c561ab191441b56d9bcefc/configs/agent/expel.yaml)
使用免费的本地Hugging Face `all-mpnet-base-v2`编码器，并非必须付费嵌入。
没有在当前链路部署该编码器或忠实完整适配，因此不能把此前借鉴规则更新算成
已经复现ExpeL。其`none`是关闭检索的变体，`random`原代码仍先相似检索再打乱，
都不能仅按名字当作无额外机制的完整强对照。

SkillCommit仍是必须引用的近邻，未核实作者仓库不等于不存在仓库；原文的编码
检索、兼容分组和层次合并不能静默删换后冒称原法。当前不宣称胜SkillCommit或
全部近期方法。若增正式方法，须在TEST首次预测前保留旧版并冻结完整修订矩阵、
实现差异及比较族，不根据ACE或TEST成绩决定是否纳入。

两项既定消融仍为whole_bank与first_commit，各一次seed45从空库完整学习128案八批，
已冻结但均未启动/排队。前者检验作用域分量提交相对整库提交，**不是全部接受**；
后者关闭跨批失败传递及首个接受后的继续细化，**不是无标签或无所有失败反馈**。
实际计算可能不同，不能归因为某条反馈信息的纯因果效应。自身B1控制另检验继续
更新是否有用；盲静态控制另检验收益是否只来自一次法条整理。已运行的主训练日志
不是这些独立消融结果。完整核对
`external_method_selection_primary_ExpeL_config_and_formal_ablation_status_20261022.json`。

新B2全部96首答原始审计已完成：技能自报按不同ID统计，原始ID列表保留，本批
没有重复ID、截断或解析错，10条技能每条均至少被自报5次；自报不证明因果使用。
对直接空库32任务6好8坏18平，平均−2.38715pp；对本方法3好16坏13平。
CPU25270与观察28878均已结束，不重复执行覆盖报告，也不采用旧Run01成绩。
下一步用70202观察唯一B2发布和全32 TRAIN，之后继续ACE全部八批；不据空B1、训练重答或
单个B2案例判断成熟方法优劣，不另起重复进程。
[最终分析计划](research/OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md)保持：
主/ACE各三次一致独立学习seed45/145/245，静态7条/2411tokens仍待性能，
whole-bank/first-commit必要消融必须实际独立学习，不能手删末库冒充。
所有矩阵、配置和末库须首次TEST预测前冻结；128来源配对cluster bootstrap20000次，
原最低八主/四次要比较保留为旧版本；下述补充将最终主要族明确扩大至十项，
不将EC/EV或三学习器复制为更多独立来源。
SkillCommit近邻须引用，无原实现/已授权原编码服务，不冒称复现或SOTA。
封存IID128 TEST未读语义/预测/标签/结果，字节hash
`6a5f72559a021d425d5b6ee41ba19f1a8e10d7da1ac11e0725d469a281c5164d`。
正式Results仍PENDING，目标未完成；当前不再把旧B8待完成状态当后续工作。

## 20:03已落实的补充对比，而非只给候选名单

依据师兄两个研究/实验skill，已选择并独立实现**Trace2Skill（文本分析、OpenExempt
适配）**，root commit `a8dd117`。它补充ACE的在线playbook路线，保留逐轨迹修改、
共同原始技能、有序分层合并及统一应用；不复用我们自己的更新/准入函数。
这是明确的文本任务重实现，不是原作者ReAct工具式系统的原样复现；不能将此变体
的输赢推广为原生完整Trace2Skill、SkillCommit或全部方法的输赢。
原文及固定作者代码已实际阅读；只引思想、没有复制未核实整体许可的runtime/提示。

三份seed45/145/245配置已分别374文件/50packages冻结，source双盘各376成员逐字核验，
均未启动或排队。每份从空库产生完整256条自己的源轨迹，标签随后释放；至多
256次分析+64次分层合并+1次计划translation。末库全文件经同直接actor预载，
8192完整tokens上限，全部256 TRAIN再答只报告不选库/seed。不新增嵌入器、模型或
服务；错误保留停止，无首条修改fallback、丢冲突、格式重抽或答案修复。
现有六个已冻结任务不变；新增三次按其真实终态后再顺序执行，当前共享账本仍3349，
未来7223/7865/8507只是各阶段预定天花板，不是已应用的扩额或实际消耗。

协议`OPENEXEMPT_TRACE2SKILL_TEXT_COMPLEMENT_20261022.md`；统计增补
`OPENEXEMPT_FINAL_ANALYSIS_TEXT_COMPLEMENT_ADDENDUM_20261022.md`已明确最终五组
EC/EV主要比较，共十项；两消融四项次要比较保持。独立学习/源配对及TEST边界不变。
完整真实末库仍未齐备，最终16臂矩阵只能在所有必要学习实际完成后冻结，不能提前
打开TEST或按新补充方法结果去掉不利的比较。

隔离评测器已接入该构建的真实文件/源记录/末库/终态/三次一致协议校验，commit
`8a55e73`。它继续保留旧统计与静态/消融闸门，纯合成相关检查58项通过，8.67秒；
新文本构建的13项结构与完整256→321→256阶段顺序检查通过，0.29秒，均不调用真实
模型/教师。隔离目录曾因官方cache软链接造成来源检查失败，已将固定公共源缓存
独立复制并逐字核同，旧链接保留，不修改共享评分源，也未动TRAIN/TEST packet。
两个分支新方法/配置/协议/小测试11文件逐字一致，但不声称隔离评测器的全部新
统计文件与旧学习清单相同。源码/配置保全与复核见
`Trace2Skill_text_three374_frozen_profiles_native_adaptation_source_dual_isolated58_and_primary10_no_TEST_audit_20261022.json`。
现稿v0.3仍是18:04的旧最低矩阵快照，正文后续须按本增补更新，不填未测方法成绩。
