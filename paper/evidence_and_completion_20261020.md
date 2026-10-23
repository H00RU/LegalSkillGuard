# 当前论文证据与完成条件

更新：2026-10-23 08:04 CST。本页只列当前可用证据和待完成内容。
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
| 完整主训练实际消耗可核 | VERIFIED | 1158native生成/生成端点HTTP全stop，7655443输入/3232344输出；15教师、3232522输入/51361输出，含拒收工作，不是全部HTTP查询数 |
| 额外B1评测是主训练后期耗时的主要来源 | CONTRADICTED | 全程实际首答/学习引用1077、仅B1评测81，原1158不减；主B6的249中169为候选重放。224个逻辑B1评测记录不能当224次额外生成，也不把1077当反事实训练时长 |
| 学得库在后续TRAIN比同案强空库更好 | VERIFIED | 完整八批表；B8 EC83.90/EV85.21%，同案空库59.12/59.96%；不是独立TEST |
| 持续进化超过首批学得库 | VERIFIED | 全112个B2–B8来源EC+0.85565/EV+9.39396pp；B2按设计差0 |
| 真正额外更新后的后续来源增益 | VERIFIED | 全96个B3–B8来源EC+0.99826/EV+10.95961pp，未删不利批次 |
| 两任务都已经表现出同等强的持续进化 | UNSUPPORTED | EV持续收益较大；EC平均不到1pp，不能说同等强或统计显著 |
| EC弱收益只是新技能投递丢失 | CONTRADICTED | 96案80案指导/原HTTP与B1相同；16案改变均真实送达，10好3坏3平 |
| 所有EC准入拒收都只是门槛过严 | CONTRADICTED | 11个实际改变分量2接收、5有原F1损害、4有完整输出/负资产损害；未来放宽效果未知 |
| 被拒EC更新确有实际条款主张损失 | VERIFIED | 全11分量内容/全改变TRAIN主张、294次前后投递/228原调用核同；B6相关56来源中至少42个原F1降，主要漏报原正确一般财产条款 |
| 泛化改写或大教师输入已被证实是因果根因 | UNSUPPORTED | 观察到具体例子改写与损害同现；15请求输入123777–246267tokens，尚未做独立干预验证 |
| 教师确实接收了冗余法律观察 | VERIFIED | 896任务视图的empty/initial答案、评分、错误等相同；调用别名元数据可异，不把全部对象字节冒充完全相同 |
| 末库残余错误仍无可核具体模式 | CONTRADICTED | 全128来源256任务完整清单逐项匹配原完整输出TP/FP/FN；EC173漏报/19误报，EV150漏报/85误报，不是新主指标 |
| 四类通用条款的140条EC遗漏都未收到技能 | CONTRADICTED | 全部对应原HTTP有明确程序；占173条漏报的80.9%，不是案件/F1损失占比；256个末库完整messages/schema/generation均与实际调用核同 |
| EV金额不足只是缺少金额规则 | CONTRADICTED | 全部八个俄勒冈(p)金额错输出400美元，题面值明确低于400且目标相同，已送规则要求取较小者；不能据此识别注意力/表示方式等因果原因 |
| 八个OR(p)金额错误全是末尾JSON损坏或都由B6新引入 | CONTRADICTED | 六个保存推理计划已写错，八个同资产联邦(d)(5)金额正确；实际B5父库是5正确变错/2漏报/1已错。全67目标主张另有14低值正确、14漏报、31上限正确；不是67独立案件或新指标，不证明单一措辞根因 |
| 末库已经做过人工法律专家验证 | UNSUPPORTED | 仅助手全文与公开数值来源审查；七记录/五EC七EV/operators空，18种美元数值有公开额度或组合来源，不能证明法律适用或排除过拟合 |
| EV指导变化与收益可复核 | VERIFIED | 96案75案改变、45好8坏22平；其余21案真实请求/回答/评分与B1相同；观察分解非因果 |
| 教师真有正确TRAIN答案及真实父观察 | VERIFIED | 15次教师、896个含重复任务标签条目逐项核同；无未来/TEST标签 |
| 分量组合与技能修改真实参与训练 | VERIFIED | 14非NOOP提案，9接收中5次整提案未过但分量组合获收；7创建14更新，0实际删除/合并 |
| 单一组合库不是逐案挑答案 | VERIFIED | 九次实际组合1152个重复TRAIN任务视图，按公开分量统一取父/提案侧；401原响应逐项复核，重新解码评分，组合新增生成0，均值分解恒等式通过 |
| B8新增WI技能影响了无关州案件 | CONTRADICTED | 九个新金额错是六个WI可选案件的联邦条款；全部229条EC/非WI-EV请求/原回答/分数不变，10个WI额度错确实修正，负面记录不删 |
| 最终B8新增技能已在更晚TRAIN得到验证 | UNSUPPORTED | B8后新增WI EV，尚无更晚TRAIN批次；末库效果须隔离评价 |
| 原生评分与完整输出审计的口径已明确 | VERIFIED | 不改变原评分；原EC负资产使满分低于1，完整输出为独立次要口径，不把两者当同一指标 |
| 当前八批无效、必须换法律任务 | UNSUPPORTED | 未发现使主轨迹作废的问题；当前对照修正不影响原主训练 |
| 已胜成熟ACE、静态与其他经验方法 | PENDING | 当前只有部分ACE首答；完整ACE/静态/文本适配及最终TEST未齐，不以早期差距充当成熟胜出 |
| 同进度前五批完整80来源的比较可核 | VERIFIED | 主方法原EC/EV81.83457/76.77827%、强空库61.55704/62.82837%、原生ACE58.63765/55.74887%；含B1，全160任务/臂原评分重算，不是完整8批/末库/TEST或显著性 |
| 主方法教师次数少就代表所有计算都更省 | CONTRADICTED | 前五批实际8B616、教师10；ACE保留548/252，另退役10/12。主585实际被学习/首答引用、31只供B1评测，不减总616、不按逻辑记录估成本；教师输入/输出分别2114578/36942与ACE6855324/231688 |
| 主方法与ACE之间的差异完全是记忆算法差异 | UNSUPPORTED | 原生ACE B1空记忆59.53/55.30%，直接空库63.45/66.35%；生成提示/外包装不同，正式比较须保留该解释边界 |
| ACE v3失败文本交给教师的方式符合上游 | CONTRADICTED | 原文只留磁盘、失败观察为null；上游向Reflector传gen_response。已针对性修复 |
| v4仍把不完整答案修成正确答案 | CONTRADICTED | 原始失败/零分/8192上限不改，只把原公开失败文本送TRAIN反思；不恢复JSON或猜ID |
| v4接续相当于多一个独立学习重复 | CONTRADICTED | 同seed45在实际最后完整B2接续；220旧生成+102教师及64完整B3首答保留一次 |
| 接续改变了B3首答或选择较好答案 | CONTRADICTED | 全96逻辑预测同原HTTP来源、法律答案、错误与评分；两条EV截断仍为0 |
| B1/B2已受此次失败文本缺失影响 | CONTRADICTED | 348保存回答无解析失败，条件修正分支在该前缀未触发 |
| v4失败公开文本与正确TRAIN标签实际进入新教师 | VERIFIED | 固定224/228 EV的完整原文、整份反思提示/schema与fresh wire逐字一致；8192截断及原零分保留 |
| B3真实技能更新且已经交给下一批执行器 | VERIFIED | 00:29:46唯一发布，12→15条/1530tokens，3ADD旧内容不改；229 EC/EV HTTP含全部15条，EV自报引用新err-00015 |
| B3训练重答改善等于B4新案改善 | CONTRADICTED | 同案4/32→27/32完全答对；完整B4 ACE49.46/56.15%，空库54.95/57.17%，不能把拟合当迁移 |
| 完整B4同案对照及技能投递可核 | VERIFIED | 16源/每臂32任务/96逻辑记录，全部15条送达；主方法83.85/79.84%；64原调用、230EC一条8192截断零分保留，不是成熟8批或TEST |
| B4实际学习及本批成本可复核 | VERIFIED | 03:07:36唯一发布15→17条/1784tokens；32完整TRAIN、2ADD、原15内容不改；3/32→24/32同案完全答对是拟合，114native/54fresh教师，不混前批/恢复调用 |
| 完整B5首答及新技能实际投递可核 | VERIFIED | 16来源/96逻辑，ACE56.875/55.94595%、同案空库55.97222/65.3125%、原主方法86.77083/80.82837%；17条全部送达；251EV、254EC长度零分保留，64次生成端点请求、472192输入/157651输出 |
| B5的EV不足仅由格式截断解释 | CONTRADICTED | 仅1/16 EV格式零分；即使假设该值变成1，其均值上界仍为62.20%，低于空库65.31%。不是改分结果，也不单独识别原生提示、语言或记忆的因果效应 |
| B5实际发布仍未完成或必须强制增加技能 | CONTRADICTED | 05:32:56完整32TRAIN后原生0ADD，17条内容保留、计数更新，1784tokens/SHA44142a6；全链独立核同。4/32→26/32是拟合；110原生成/51新教师，两条截断零分保留 |
| B6全部96首答、实际父库与原分数已核 | VERIFIED | 07:01:38完整，原ACE62.70833/57.06019%、空库56.31055/67.72321%、主方法84.60317/83.43502%；17条全部送达，261EC/EV两长度零分保留；64生成476048输入/182121输出 |
| B6唯一发布与全部32TRAIN已独立核完 | PENDING | 原进程继续反思；07:54:26迁至B6只读用户服务1587788，等待实际发布后核全32轨迹/正确标签/计数/成本并双盘保全，仅一次只读分词元数据，不额外作答 |
| 只读观察器退出意味着训练也退出或需重跑 | CONTRADICTED | 旧工具汇总89759以143退出，确切来源未定；原训练/模型/两排队句柄均未变。三个观察任务已迁服务器用户服务，实际启动和脚本SHA见launch queued.json，不更改算法、预算或模型 |
| TCPStore心跳告警意味着模型已经退出 | CONTRADICTED | 原API/engine/ACE及两等待PID、argv/start仍在，GPU97%，日志仍有生成；完整B5及新TRAIN调用继续完成。确切store-peer原因未定，没有停训或重启服务 |
| B3接续批成本可核且未重复算前缀 | VERIFIED | 原64首答+40新TRAIN生成共104native；45fresh教师；退役10/12与前两批另计 |
| 原失败成本被丢弃 | CONTRADICTED | 旧Run02完整294native/114教师双盘1643成员；退役B3的10native/12教师单列，不导入新训练 |
| 完整静态TRAIN控制已经跑出成绩 | PENDING | run02配置400/50冻结，PID821776仅Bash等待完整ACE；固定原7条/2411token、零新教师 |
| 同接口文本对照已自动衔接且已完成学习 | PARTIAL | 02:51:53具体交接unit已启动，PID1130167只等待原静态；无Text运行目录或新调用。完整主/ACE/静态与终态保全后才扩额3349→3991并启动一次Text45 |
| 九个后续学习profile仍可按当前代码执行 | VERIFIED | 新23日377/383/378文件版本冻存双盘，02:30当前字节/50packages匹配，全未启动；旧22日版保留不再作启动入口 |
| 为提前比较而改了文本学习算法 | CONTRADICTED | 只把无关前序学习器数量8→2，运行时自然完成/无failure/保全/同锁检查保留；归纳/合并/翻译/执行AST未改，13合同及算法字段核验通过 |
| 三次独立学习、两项消融已完成 | PENDING | 当前只有主seed45；其余真实实验仍须执行，不以CPU结构检查替代 |
| Trace2Skill对照是原工具式作者复现 | UNSUPPORTED | 已实现的是text-analysis/OpenExempt适配，三个profile未启动，差异须披露 |
| 已优于SkillCommit/全部SOTA | UNSUPPORTED | 最近邻只作机制/引用比较，未量化复现；custom profile不能裸比分数冒充官方Advanced榜单 |
| 正式评价实现已接入v4与同一学习器接续来源 | VERIFIED | 核心4acdae2通过83合成；81333d9保留来源/原空库/最后B2/1301哈希/全B3与退休成本检查，准备并发调度并约束相同端点；真实TEST未读 |
| 完整评测的并发加速已经实际部署 | PARTIAL | 隔离入口106项CPU检查20.81s通过，原stdout存档，13执行器副本/11profile/50packages匹配；默认串行保留，当前单序列环境拒绝四请求模式。尚无真实四并发配置、服务切换或实测速度 |
| 正式16-arm TEST矩阵现在已经可运行 | PENDING | 所有实际末库/重复尚未齐；唯一正式CLI拒绝不完整设计，不能启动TEST |
| 相关工作已补机制分类及四条主来源 | VERIFIED | v0.10中英两主题，原四文献逐字保留；新增ExpeL/工作流记忆/ReasoningBank/兼容性审计，不表示已复现新增方法；摘要/方法/结果/表/科学数字不改，41链接及11绑定通过 |
| 已有可直接审阅的完整双语PDF | VERIFIED | 内部审阅20页含附录D，330文本单元/6表/两幅已有图，实际PDF文本差异0、关键页检查；源M/D逐字v0.10、待填高亮，不是正式投稿版或实验已完成 |
| 真实TEST已经用于调优 | CONTRADICTED | 目前只允许字节哈希；语义/标签/预测/结果未读，无验证集 |

## 已完成证据入口

以下均在`artifacts/research/openexempt_legal_scope_20261020/`，不是新模型调用：

- `Run03_learning_curve_complete_first8_final8_publications_20261022.json`
- `Run03_complete_B1_B8_actual_terminal1158_15_cost_20261022.json`
- `Run03_complete128_first_forecast_actual_skill_projection_vs_own_B1_736_native_record_delivery_and_newcase_effect_decomposition_20261022.json`
- `Run03_all15_teacher14_candidate8_publication_actual_scope_composition_and_library_management_accounting_20261022.json`
- `Run03_all9_actual_compositions1152_TRAIN_views_public_side_raw_reuse_fresh_decode_and_mean_identity_20261023.json`
- `Run03_B8_ten_WI_repairs_and_nine_federal_errors_same_WI_cases_no_nonWI_case_interference_clarification_20261023.json`
- `Run03_all_postB1_EC11_changed_components8_proposals_actual_parent_scope_gate_failure_bottleneck_20261022.json`
- `Run03_all128_TRAIN_native_target_self_F1_ceiling_and_residual_headroom_20261022.json`
- `Run03_all11_EC_actual_changed_guidance_and_all_TRAIN_claim_transitions_raw_delivery_NOT_causal_20261023.json`
- `Run03_all15_actual_teacher_payload_sizes_and896_duplicate_legal_control_views_alias_metadata_disclosed_NOT_quality_cause_20261023.json`
- `ACEv3_Run02_B3_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261022.json`
- `ACEv3_Run02_B3_failed_public_output_reflector_data_loss_safe_stop294_114_and_valid_prefix_evidence_20261022.json`
- `ACEv3_Run02_last_completed_B2_and_complete_B3_first_forecast_continuation_receipt_20261022.json`
- `ACEv4_actual284_102_prefix_and_all96_unchanged_B3_forecasts_failed_public_trace_CPU_audit_20261022.json`
- `ACEv4_actual224_228_failed_public_text_correct_targets_full_fresh_teacher_wire_verified_20261023.json`
- `ACEv4_Run03_B3_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_Run03_actual_B3_three_ADD_and_first_B4_source229_all15_verbatim_delivery_NOT_scores_20261023.json`
- `ACEv4_Run03_B4_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261023.json`
- `ACEv4_Run03_B4_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_Run03_B5_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261023.json`
- `ACEv4_Run03_B5_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_B5_full96_new_bullet_uses_EV_format_bound_and_nonterminal_NCCL_warning_observation_20261023.json`
- `Run03_final_B8_bank_complete128_TRAIN_replay_reference_for_mature_text_NOT_prequential_or_TEST_20261023.json`
- `Run03_final128_TRAIN_all256_exact_complete_output_residual_claim_inventory_NOT_new_metric_or_causal_20261023.json`
- `Run03_final128_raw_delivery140_explicit_general_omissions_and8_public_value_cap_errors_NOT_causal_20261023.json`
- `Run03_final7_skill_content_public_caps_vs_blind_static_assistant_review_v02_20261023.json`
- `Run03_vs_ACEv4_complete_B1_B5_equal80_prequential_original_metrics_and616_548_retired10_12_cost_NOT_final_TEST_20261023.json`
- `Run03_complete128_all1158_native_core_vs_fixedB1_only_actual_role_attribution_not_counterfactual_20261023.json`
- `Run03_complete128_actual1077_core81_B1only_cost_role_analysis_dual_preservation_20261023.json`
- `Run03_final128_ORp_all67_claims_wrong8_correct14_parent_regression5_and_saved_reasoning_NOT_causal_20261023.json`
- `ACEv4_Run03_B6_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261023.json`
- `prospective_priority_first_common_actor_text_full9_new_profiles_frozen_no_active_change_20261023.json`
- `prospective_priority20261023_operational_semantics_early2_legacy8_canonical_entry_source_validation_20261023.json`
- `hourly0230_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `implemented_method_figure_v03_actual_source_visual_links_vector_and_unchanged_v06_curve_QA_20261023.json`
- `manuscript_v07_exact_tables_abstracts_refs46_points_composition_scope_and_priority_source_QA_20261023.json`
- `manuscript_v08_evidence_led_main_complete_lineage_D_exact_tables_abstracts_refs46_points_QA_20261023.json`
- `text45_after_exact_static_run02_waiter1130167_dual_queued_no_active_budget_change_20261023.json`
- `hourly0330_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0530_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0630_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0730_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `manuscript_v010_related_work_primary_refs_exact_v09_scientific_body_11profiles_QA_20261023.json`
- `frozen_eval_four_worker_cpu105_exact_cache_failure_drain_active11_unchanged_serial91h_scenario_NOT_deployed_20261023.json`
- `frozen_eval_parallel_dispatch_endpoint_bound_final_CPU_check_stdout_20261023.json`
- `frozen_eval_four_worker_cpu106_endpoint_exact_cache_drain_active11_unchanged_NOT_deployed_20261023.json`

## 论文与剩余实验

[当前初稿v0.10](manuscript_v1_20261021.md)和[实验附录D](appendix_experimental_details_20261022.md)
描述真实直接回答、标签辅助、公开法律作用域提交与有界TRAIN反馈。
[完整v0.6](revisions/manuscript_v06_20261023_0235.md)及其附录D逐字保留。
[完整v0.7](revisions/manuscript_v07_20261023_0259.md)及其附录D也逐字保留。
[完整v0.8](revisions/manuscript_v08_20261023_0452.md)及[同期附录D](revisions/appendix_D_v08_20261023_0452.md)逐字保留。
[完整v0.9](revisions/manuscript_v09_20261023_0627.md)及[同期附录D](revisions/appendix_D_v09_20261023_0627.md)也已逐字保留。
图1完整46个F1点/六条折线坐标不改，B8发布状态已更新，SVG/PDF/600dpi PNG可用。
[方法总览与双语图注](figures/method_overview_caption_20261023.md)另行完成，明确标签释放
时机、全部已见TRAIN重放、公开编辑依赖、分量组合与下一批使用；无新成绩/虚构分组。
Georgia不可用，沿用图1实际DejaVu Serif；图像、两版摘要和所有表行不变。
v0.7补真实组合/成本证据、纠正B8法条与案件范围歧义及更新未来操作顺序；
v0.8将源码与适配器修复沿革归入附录，正文突出方法及实际收益，所有指标不变，待整合图号。
v0.9精简正文的内部版本前言，明确1158只计生成端点HTTP，不含分词和就绪查询；
不改任何科学效果、生成成本数值、摘要、表、图或参考文献。
v0.10补两主题相关工作及ExpeL、AWM、ReasoningBank、执行兼容性审计四条已核主来源；
旧四条参考文献保留，摘要、方法、结果和表及所有科学数值逐字不变，附录正文不变。
它不新增实验臂，也不借引用声称已复现或验证这些方法；41条本地链接及11绑定匹配。
[内部双语PDF](../artifacts/research/manuscript_review_20261023/v010_bilingual_internal_v03/legal_skill_evolution_v010_bilingual_internal_review.pdf)
完整保留上述源稿及附录D，既有两图嵌入，20页是合排审阅长度，不是英文投稿版页数。
[最终图文核对](../artifacts/research/manuscript_review_20261023/v010_bilingual_internal_v03/final_review_QA_20261023.json)
绑定源稿、PDF、330文本单元/6表、字体、关键页和重现程序，不改数据或学习链。
正文不以工程组件、更多技能或接口支持操作数冒充创新；近邻机制须正确归属。
已核实参考条目不因润色改标题或作者；新引用仍须主来源核实。

最终计划16arms、5比较家族×EC/EV=10主要比较、两单seed消融×EC/EV=4次要比较。
128来源配对bootstrap20000，PCG64seed2026102192；区间条件于实际库和固定评价seed45。
不把3库变成384来源，不从单轨迹造学习误差带或显著性。
全部真实末库/完整矩阵/统计与评价源码必须在第一条TEST预测前冻结。
当前4096逻辑预测按主Run文件区间均值作不复用串行情景为91.58h，不是实际TEST
耗时或ETA。隔离调度准备不减少16臂/128来源或推理预算，也未改变当前模型服务。

完整ACE与静态TRAIN后先完成共同执行器Text45，再投入其他重复。若TRAIN证据
不足以支持方法收益，就继续TRAIN根因优化与新运行，
并重新完成受影响的正式学习比较。论文写作与这些实验并行，不能只停在清单、
历史审计或等待结果，也不能提前填上尚未得到的优越性结论。

Text是离线构建，未来的末库TRAIN拟合必须与本方法实际末库的完整128来源重放
对齐，不能直接与各批当时的在线首答比较。现有B8组合已提供全256任务参照，
原F1 EC86.03/EV89.30%，新增生成为零；本方法已在这些样本上准入优化，
因此该比较偏向本方法，只作TRAIN诊断，不替代原曲线或正式TEST。
