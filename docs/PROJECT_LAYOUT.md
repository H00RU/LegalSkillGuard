# 项目目录与工作入口

整理日期：2026-10-16。这里只整理入口和说明，不改运行中的冻结文件。

## 当前项目

- 日常入口：`/home/yndx/hhy/legal-skill-current`，软链接到下述实际目录。
- 实际目录：`/media/sangfor/vdb/legal-skill-evolve`，唯一当前源码，不另复制一套到 home。
- `legal_skill_guard/`：律师推理、技能学习、查询执行、评分及实验核心代码。
- `configs/`：配置与对应冻结清单；不是所有保留配置都已启动。
- `runs/<Run ID>/`：各次实验的冻结输入、运行时源码快照、实际模型输出、技能版本与进度。
- `reports/experiments/`：预先确定的协议及已完成部分的审计说明；失败试验也保留。
- `docs/`：方法、历史决策、重建边界及当前研究目标。
- `data/`、`artifacts/`：数据与可追溯工件；不是临时清理目录。
- `third_party/`：实际采用的上游实现及许可证；`tests/` 是小规模边界测试。

## 当前后台工作

08:08:58另已后台排队`legal_contractnli_evidence_scope_ablation_20261016_run01`，PID3439428，
固定26新律师/0教师，等待精确ACE PID3360667及GPU锁后自动接续，不依赖对话。
只从当时真实M1—M4库移除nda-complete-operative-evidence及必要ID元数据，全部其余文字/模型不变。
覆盖全部18首遇＋8暴露开发，52旧回答明确引用，非新主训练、正式确认或效果准入。
driver仅本Run归档，协议在grounded_feedback报告目录；667绑定与当前ACE的663都冻结至各自退出。
显式status --run-id legal_contractnli_evidence_scope_ablation_20261016_run01查看队列。

最新：10月16日07:18启动`legal_contractnli_ace_same_data_20261016_run01`（PID3360667），
同24原TRAIN/四批6/同原证据模型的原生ACE法律适配比较，计划52新律师/28教师；663绑定冻结至退出。
用`.venv/bin/python -m legal_skill_guard.cli status --run-id legal_contractnli_ace_same_data_20261016_run01`查看。
原生生成提示/计数/ADD管理及自身空playbook控制保留，真实8B trace可用于反思；非新主方法或正式测试。
case-credit PID3292117已07:00:22完整16/8自然结束，逐案组86.03/69.83/59.56%，未解决依据/联合目标，不部署额外层。
delivery PID3248203已06:21:10完整16/0结束，coherent86.03/70.43/58.82%、flat81.62/72.10/54.41%。
coherent分类净+7全来自374，不是稳定迁移或完整在线进化，不升为已修复主方法。
compiler前序3239414已06:01:33失败退出，0律师/1教师：平面4409超限，分支3183；失败保留。
新delivery仅平面去纯排版标题/缩短ID至4073，法律字句原样、4096上限不变，复用原教师非重试。
前一`legal_contractnli_grounded_final_assessment_20261016_run01`已05:48:10自然完成44律师/0教师并退出；
真实末M4开发83.09/69.91/59.56%，同工具80.88/71.37/55.15%（分类/F1/联合），尚未稳定胜等信息控制。
父`legal_contractnli_grounded_feedback_20261016_run01`因完整B4严重损害于04:52:09停止，78律师/5教师；
M4在停止收尾时已发布但无律师执行。原失败/停止保留，当前评估不等于新正式训练、原worker成功或独立重复。
CLI默认仍指向停止父Run；旧评估32终点已全答核验后评分，新诊断16新答/32继承对照重放后才评分。
原子接续2867332已02:50:22完成52新答，配对2867347已03:00:08完成8新答/1教师，
关系诊断2957831已03:07:22完成8新答/0教师；都不再运行，负面结果不隐藏。

以下为已终止父实验的历史启动记录；旧默认研究为`legal_contractnli_atomic_boundaries_20261015_run01`，
配置`contractnli_atomic_boundaries.json`，协议[ATOMIC_BOUNDARY_METHOD](ATOMIC_BOUNDARY_METHOD.md)。
计划四批每批6份原TRAIN、130新律师/6教师，含同标签普通工具、静态和最后更新输入控制。
新Run已于10月15日23:58:24真实后台启动（PID2697441）；实时阶段核实启动记录/进程/progress，不能由配置推断。
当时10月16日01:12:21另排队最后更新配对反馈诊断（旧PID2806817，8律师/1教师计划），
该旧队列随后因父未完成而取消0调用，不应与后来完成的run02或当前新训练混用。
上一程序学习20:56:22启动、23:26:23完成130律师/6教师，去候选23:33:00完成6新律师；两个进程均已退出。
此前查询学习20:09:59停止于64新律师/4教师，B1—B3完整、B4部分；
法律步骤旁路20:19:50完成8新律师/1教师，未建立稳定收益。
真实启动时间/PID以`artifacts/launches/`记录及实际进程共同核实，不能由配置推断已在运行。
紧凑交付诊断已17:28:14完整结束，36新律师/0教师，未胜强空库整体指标。
已结束worker使用冻结生产入口，运行时不改绑定源码，不重跑旧Run或伪造默认status。
旧三条件/多条件有限试验**不是已经完成的正式论文比较**。
早期自适应对照Run启动时在普通对话实施，未开Goal；不能将此描述套用于18:56的查询Run。
15:09用户明确要求新建Goal，现为active；最新目标与执行顺序见[CURRENT_GOAL](CURRENT_GOAL.md)。

| Run ID | 用途 | 查看进度 |
| --- | --- | --- |
| `legal_contractnli_feedback_completion_20261015_run01` | 已完成124个全链物理律师调用、14教师响应及四来源探针，未建立稳定优势 | `completion.json`及独立八来源`main_completion.json`，进程已退出 |
| `legal_contractnli_adaptive_memory_comparison_20261015_run01` | Schema拒绝后失败，2新律师/0教师响应/1请求尝试；工件保留 | `failure.json`，不是仍在等待或方法效果失败 |
| `legal_contractnli_adaptive_memory_comparison_20261015_run02` | 13:47完成58新律师/16教师/2共享冷答；没有整体胜过强空库 | `completion.json`与`results.md`；失败费用见`restart_provenance.json` |
| `legal_contractnli_answer_review_learning_20261015_run01` | 15:31:45完成四批及后续24答；有小幅联合收益，无等调用依据F1收益 | `completion.json`，56新律师/4教师/2共享，进程已退出 |
| `legal_contractnli_answer_review_anchor_diagnostic_20261015_run01` | 15:41:06完成固定4个已见TRAIN来源的初答依据干预，10新律师/0教师 | `completion.json`与独立审计；不是训练或论文主成绩 |
| `legal_contractnli_source_check_learning_20261015_run01` | 16:37:39因B3过选/联合损害安全停止，26新律师/3教师，B4仅部分 | `progress.json`、`failure.json`及独立审计；进程已退出，无新8来源结果 |
| `legal_contractnli_cpu_evidence_signal_20261015_run01` | 16:18:51完成四累计监督证据排序，仅旧已暴露开发来源 | `completion.json`及独立审计，0律师/0教师，不是主任务成绩 |
| `legal_contractnli_evidence_ranked_delivery_20261015_run01` | 16:33排队，16:37随父停止取消，0调用 | `failure.json`，进程已退出，不覆盖重启 |
| `legal_contractnli_compact_evidence_delivery_20261015_run01` | 17:28:14完成36新律师，未胜空库整体指标 | `completion.json`、`independent_complete_audit.json`，进程已退出 |
| `legal_contractnli_cpu_signal_scale_20261015_run01` | 17:18:51完成6/12/18/24监督量检查，非律师终答收益 | `completion.json`，0律师/0教师，进程已退出 |
| `legal_contractnli_evidence_operator_learning_20261015_run01` | 18:36:45因47查询实际作用为0停止，14新律师/2教师，B1完整 | `progress.json`/独立停止审计，无后续8答案 |
| `legal_contractnli_query_memory_learning_20261015_run01` | 20:09:59安全停止，64新律师/4教师，未整体赢同标签普通工具 | `progress.json`、三批摘要及`monitoring/stopped_run_and_library_lifecycle_audit.json`；无M4/后续8答 |
| `legal_contractnli_decision_procedure_delivery_20261015_run01` | 20:19:50完成法律判断步骤诊断，4来源/8新律师/1教师 | `completion.json`；相对教师新2案依据F1下降，不是方法已成功 |
| `legal_contractnli_final_query_objective_20261015_run01` | 20:18:57完成最终概率查询损失CPU对照，无净F1收益 | `completion.json`，0新律师/教师，仅旧已暴露8开发来源 |
| `legal_contractnli_trace_procedure_learning_20261015_run01` | 23:26:23完整结束，130新律师/6教师，技能增益仍小 | `completion.json`与独立完整审计，进程已退出 |
| `legal_contractnli_M2_tool_influence_20261015_run01` | 23:33:00完整结束，6新律师/12明确参考，去候选使三指标下降 | `completion.json`与独立18答重算，进程已退出 |
| `legal_contractnli_atomic_boundaries_20261015_run01` | 01:30:29因容量计量不一致失败，78物理律师/12共享/5教师保留；主M4未调用 | failure与停止重放审计，PID2697441已退出，无终点答案 |
| `legal_contractnli_paired_final_update_20261016_run01` | 01:30:34随父未完成取消，0律师/0教师 | cancellation与终态progress，PID2806817已退出 |
| `legal_contractnli_atomic_completion_20261016_run01` | 02:50:22完成52新律师/1教师，加祖系共130物理答 | completion与完整审计；不是从空库独立重训 |
| `legal_contractnli_paired_final_update_20261016_run02` | 03:00:08完成8新律师/1教师，三指标较主更差 | completion与真实教师/8答独立审计；非完整配对学习 |
| `legal_contractnli_M4_relation_channel_20261016_run01` | 03:07:22完成8新律师/0教师，统一去关系三指标更差 | completion与差异/原评分审计；不默认部署 |
| `legal_contractnli_grounded_feedback_20261016_run01` | 04:52:09因完整B4三项严重损害安全停止，78律师/5教师 | 实际M4已发布/工具拟合但未执行；原停止保留，不称完整成功 |
| `legal_contractnli_grounded_final_assessment_20261016_run01` | 05:48:10完整结束44新律师/0教师 | completion及32齐答后原Gold评分，祖系122/5；非独立训练 |
| `legal_contractnli_contrastive_procedure_20261016_run01` | 06:01:33容量失败，0律师/1教师保留 | coherent3183/flat4409，未生成律师回答，PID3239414退出 |
| `legal_contractnli_contrastive_delivery_20261016_run01` | 06:21:10完整16新律师/0新教师 | completion及原作者独立重算，分类提升集中374，非稳定迁移 |
| `legal_contractnli_case_credit_20261016_run01` | 07:00:22完整结束16新律师/8教师 | completion及原作者独立复算；额外反思不部署为主方法 |
| `legal_contractnli_ace_same_data_20261016_run01` | 07:18启动同24案ACE法律适配比较，计划52新律师/28教师 | PID3360667、663冻结绑定；同8B/工具、原生actor与empty控制 |
| `legal_contractnli_nli_signal_20261016_run01` | 00:46:07完成固定规则条件的CPU分类信号诊断，无稳定额外收益 | completion与独立816预测复算；0律师/教师，不部署为法律裁判 |
| `legal_contractnli_query_sample_size_20261015_run01` | CPU旧查询库24/64/128样本量诊断；首24拟合后严格模型一致断言失败 | 22:25:05已退出，0律师/教师，未读评价Gold，失败工件保留 |
| `legal_contractnli_query_sample_size_20261015_run02` | 同诊断仅统一原生线程环境后全部重做；固定旧库无净F1收益 | 22:36:52完成6次CPU拟合，0律师/教师；只读旧暴露8来源，不是当前主任务成绩 |

旧 `legal_contractnli_grounded_feedback_learning_20261015_run01` 于10:11在B4强制教师审计引用检查处失败，
44个律师回答和7个教师输出保留。旧 `grounded_references` 随父失败停止，已完成5个教师发布但0律师回答；
旧 `literal_receipt_delivery` 因依赖失败停止、0新调用。这三者都不冒充仍在训练。
新分叉不改写这些失败记录，继承真实检查点与独立有效参考库，去掉B4强制coverage自报并重新调用教师。
它使用明确修订过的开发协议，不是从头同一预注册干预，也不是独立学习重复。

后台进程不依赖对话持续采样。实时状态以进度、真实模型工件和完成/失败记录共同核对，
不能把本说明中的阶段描述当成完成证据。不要重复运行这些 worker。

`configs/contractnli_main.json` 是另外保留的 388 次律师调用完整比较配置，
尚未启动；它已经不是默认CLI入口，不应与当前方法混用。

## 历史恢复材料与备份

| 位置 | 身份 |
| --- | --- |
| `/home/yndx/hhy/legal-skill-archive` → `/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln` | 恢复档案总入口，含旧 Git 镜像、幸存临时源码、对话修改回执及重建证据 |
| `/home/yndx/legal-skill-recovery-20261015.8k6bZM` | 文件丢失后首先建立的约 699 MB 原始保全目录，不是新项目 |
| 上述归档目录内同名 `legal-skill-recovery-20261015.8k6bZM/` | 原始保全件的副本；本次整理用 `diff -qr` 核对目录树及全部文件内容一致 |
| `/home/yndx/hhy/legal-skill-backups` → `/media/sangfor/vdb/legal-skill-backups` | 已校验的源码 bundle、配置与实际实验工件备份 |
| `/media/sangfor/vdb/legal-skill-runtime` | 新项目的 Python 运行时，不是另一套业务源码 |
| `/home/yndx/hhy/legal-skill-evolve` | 旧项目幸存残留；旧模型服务参数仍引用它，不搬动、不当作当前工作树 |
| `/home/yndx/hhy/归档/` | 本轮已逐份比较的旧版六主题技能；12:36核查路径已不存在，本助手未删除，当前运行不依赖它 |
| `/home/yndx/hhy/paper-skills/` | 当前七主题论文技能，覆盖上述六主题并增加找idea；两版不是逐字相同 |

恢复目录中的 `README.md` 记录的是当时的取证状态，早期 `reconstructed_source_v2/v3`
也只是恢复过程产物，不代表当前代码版本。归档中的旧聊天记录和聚合指标不能替代已丢失的原始模型回执。

本次没有删除任何恢复材料，没有覆盖原始取证文档，也没有移动实际项目、模型路径、
冻结源码、原生输出或教师记录。软链接只是统一访问入口，不增加源码副本。
vdb 上的多个目录不等于已具备异机/离线备份。
