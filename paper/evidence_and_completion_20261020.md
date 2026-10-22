# 当前论文证据与完成条件

更新：2026-10-22 23:41 CST。本页只列当前可用证据和待完成内容。
此前1130行开发与历史轨迹清单逐字保存在
[历史证据快照](revisions/evidence_before_ACEv4_20261022_2212.md)，不是当前结果表。
执行入口与句柄见[CURRENT_GOAL](../docs/CURRENT_GOAL.md)。

## 科学主线

研究冻结8B如何通过连续编辑可复用的法律程序性技能改善后续来源的规则适用。
原生EC评资产适用法条，EV还评法条对应金额。不是三分类、文书匹配、客户模拟、
参数微调或无标签TFGRPO。主文突出机制、训练收益、完整对比；调试细节不占据主线。
必要的监督、信息边界、成本、失败及影响结论的局限仍如实披露。

已完成主训练是有效的一次开发轨迹，不是必须守住的最终方法。若完整TRAIN对照
或末库收益不足，依据TRAIN找根因再优化并重训。正式TEST不用来反复选择方法/库。
不能把原先已见开发来源改名为未见测试；不删不利对照或美化原始分数。

## 当前证据账本

| 主张 | 状态 | 原始支持或缺口 |
|---|---|---|
| 主Run03完整128来源、8批、256任务、8次唯一发布 | VERIFIED | completion自然完成，无failure；实际全部首答与发布齐全 |
| 所有本批回答先于本批标签和教师反馈 | VERIFIED | execute顺序、原始input/HTTP/answer、评分与教师记录；回放不替换首答 |
| 主执行器/评分没有随ACE修改而变化 | VERIFIED | 原6896246四个主actor/scorer仍匹配371绑定；不是整份旧源码当前未变 |
| 完整主训练实际消耗可核 | VERIFIED | 1158native/HTTP全stop，7655443输入/3232344输出；15教师、3232522输入/51361输出，含拒收工作 |
| 学得库在后续TRAIN比同案强空库更好 | VERIFIED | 完整八批表；B8 EC83.90/EV85.21%，同案空库59.12/59.96%；不是独立TEST |
| 持续进化超过首批学得库 | VERIFIED | 全112个B2–B8来源EC+0.85565/EV+9.39396pp；B2按设计差0 |
| 真正额外更新后的后续来源增益 | VERIFIED | 全96个B3–B8来源EC+0.99826/EV+10.95961pp，未删不利批次 |
| 两任务都已经表现出同等强的持续进化 | UNSUPPORTED | EV持续收益较大；EC平均不到1pp，不能说同等强或统计显著 |
| EC弱收益只是新技能投递丢失 | CONTRADICTED | 96案80案指导/原HTTP与B1相同；16案改变均真实送达，10好3坏3平 |
| 所有EC准入拒收都只是门槛过严 | CONTRADICTED | 11个实际改变分量2接收、5有原F1损害、4有完整输出/负资产损害；未来放宽效果未知 |
| EV指导变化与收益可复核 | VERIFIED | 96案75案改变、45好8坏22平；其余21案真实请求/回答/评分与B1相同；观察分解非因果 |
| 教师真有正确TRAIN答案及真实父观察 | VERIFIED | 15次教师、896个含重复任务标签条目逐项核同；无未来/TEST标签 |
| 分量组合与技能修改真实参与训练 | VERIFIED | 14非NOOP提案，9接收中5次整提案未过但分量组合获收；7创建14更新，0实际删除/合并 |
| 最终B8新增技能已在更晚TRAIN得到验证 | UNSUPPORTED | B8后新增WI EV，尚无更晚TRAIN批次；末库效果须隔离评价 |
| 原生评分与完整输出审计的口径已明确 | VERIFIED | 不改变原评分；原EC负资产使满分低于1，完整输出为独立次要口径，不把两者当同一指标 |
| 当前八批无效、必须换法律任务 | UNSUPPORTED | 未发现使主轨迹作废的问题；当前对照修正不影响原主训练 |
| 已胜成熟ACE、静态与其他经验方法 | PENDING | 当前只有部分ACE首答；完整ACE/静态/文本适配及最终TEST未齐，不以早期差距充当成熟胜出 |
| ACE v3失败文本交给教师的方式符合上游 | CONTRADICTED | 原文只留磁盘、失败观察为null；上游向Reflector传gen_response。已针对性修复 |
| v4仍把不完整答案修成正确答案 | CONTRADICTED | 原始失败/零分/8192上限不改，只把原公开失败文本送TRAIN反思；不恢复JSON或猜ID |
| v4接续相当于多一个独立学习重复 | CONTRADICTED | 同seed45在实际最后完整B2接续；220旧生成+102教师及64完整B3首答保留一次 |
| 接续改变了B3首答或选择较好答案 | CONTRADICTED | 全96逻辑预测同原HTTP来源、法律答案、错误与评分；两条EV截断仍为0 |
| B1/B2已受此次失败文本缺失影响 | CONTRADICTED | 348保存回答无解析失败，条件修正分支在该前缀未触发 |
| 原失败成本被丢弃 | CONTRADICTED | 旧Run02完整294native/114教师双盘1643成员；退役B3的10native/12教师单列，不导入新训练 |
| 完整静态TRAIN控制已经跑出成绩 | PENDING | run02配置400/50冻结，PID821776仅Bash等待完整ACE；固定原7条/2411token、零新教师 |
| 九个后续学习profile仍可按当前代码执行 | VERIFIED | 新374/380/375文件版本已冻结并双盘保存，23:30全部当前字节/50packages匹配，均未启动 |
| 三次独立学习、两项消融已完成 | PENDING | 当前只有主seed45；其余真实实验仍须执行，不以CPU结构检查替代 |
| Trace2Skill对照是原工具式作者复现 | UNSUPPORTED | 已实现的是text-analysis/OpenExempt适配，三个profile未启动，差异须披露 |
| 已优于SkillCommit/全部SOTA | UNSUPPORTED | 最近邻只作机制/引用比较，未量化复现；custom profile不能裸比分数冒充官方Advanced榜单 |
| 正式16-arm TEST矩阵现在已经可运行 | PENDING | 所有实际末库尚未齐；隔离评价还需接续来源闸门与v4 actor同步，不能启动TEST |
| 真实TEST已经用于调优 | CONTRADICTED | 目前只允许字节哈希；语义/标签/预测/结果未读，无验证集 |

## 已完成证据入口

以下均在`artifacts/research/openexempt_legal_scope_20261020/`，不是新模型调用：

- `Run03_learning_curve_complete_first8_final8_publications_20261022.json`
- `Run03_complete_B1_B8_actual_terminal1158_15_cost_20261022.json`
- `Run03_complete128_first_forecast_actual_skill_projection_vs_own_B1_736_native_record_delivery_and_newcase_effect_decomposition_20261022.json`
- `Run03_all15_teacher14_candidate8_publication_actual_scope_composition_and_library_management_accounting_20261022.json`
- `Run03_all_postB1_EC11_changed_components8_proposals_actual_parent_scope_gate_failure_bottleneck_20261022.json`
- `Run03_all128_TRAIN_native_target_self_F1_ceiling_and_residual_headroom_20261022.json`
- `ACEv3_Run02_B3_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261022.json`
- `ACEv3_Run02_B3_failed_public_output_reflector_data_loss_safe_stop294_114_and_valid_prefix_evidence_20261022.json`
- `ACEv3_Run02_last_completed_B2_and_complete_B3_first_forecast_continuation_receipt_20261022.json`
- `ACEv4_actual284_102_prefix_and_all96_unchanged_B3_forecasts_failed_public_trace_CPU_audit_20261022.json`
- `hourly2330_ACEv4_Run03_actual380_nine_rebased_profiles_static400_original_model_and_direction_20261022.json`

## 论文与剩余实验

[当前初稿v0.6](manuscript_v1_20261021.md)和[实验附录D](appendix_experimental_details_20261022.md)
描述真实直接回答、标签辅助、公开法律作用域提交与有界TRAIN反馈。
[完整v0.5](revisions/manuscript_v05_20261022_2335.md)逐字保留。
图1完整46个F1点/六条折线坐标不改，B8发布状态已更新，SVG/PDF/600dpi PNG可用。
正文不以工程组件、更多技能或接口支持操作数冒充创新；近邻机制须正确归属。
已核实参考条目不因润色改标题或作者；新引用仍须主来源核实。

最终计划16arms、5比较家族×EC/EV=10主要比较、两单seed消融×EC/EV=4次要比较。
128来源配对bootstrap20000，PCG64seed2026102192；区间条件于实际库和固定评价seed45。
不把3库变成384来源，不从单轨迹造学习误差带或显著性。
全部真实末库/完整矩阵/统计与评价源码必须在第一条TEST预测前冻结。

完整ACE与静态TRAIN结果若不足以支持方法收益，就继续TRAIN根因优化与新运行，
并重新完成受影响的正式学习比较。论文写作与这些实验并行，不能只停在清单、
历史审计或等待结果，也不能提前填上尚未得到的优越性结论。
