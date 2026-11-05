# 第8次主方法：英文论文初稿与实验交付

交付日期：2026-11-01，Asia/Shanghai。英文为投稿主稿，中文为单独的辅助稿。
两种语言各有自己的 Markdown、Word 和 PDF 文件，不是中英混排论文。

## 1. 稿件入口

- 英文主稿：[Word](../../artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/utility_v6_working_en.docx)、[PDF](../../artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/utility_v6_working_en.pdf)、[Markdown 源稿](../../paper/utility_skill_manuscript_working_20261030.md)。
- 中文辅助稿：[Word](../../artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/utility_v6_working_zh.docx)、[PDF](../../artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/utility_v6_working_zh.pdf)、[Markdown 源稿](../../paper/sections-zh/utility_skill_manuscript_working_20261030.md)。
- [上一问所需的完整工作报告](WORK_REPORT_FROZEN_TEST_20261101.md)单列保存，不把工作日志写成论文正文。

英文18页，中文16页；两稿均有10张表、23个原生Word公式、2幅图。
这是内容与结果齐全的初稿，不冒充已完成目标期刊模板、作者信息或投稿手续。
实验与附录规范用于组织研究问题和机制证据；论证组织原则用于围绕有证据的贡献组织叙事，数值和比较条件不因此改变。

## 2. 完整实验与当前主张

主方法 `legal_openexempt_complete_output_utility_public_assets128_20261030_run01`
完成128源、8批、16次教师响应。C1严格准入策略及C2教师显式执行证据移除控制
也分别完成相同8批。新来源隔离冻结测试
`legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01`
完成10条件×128源×EC/EV，共2560次真实预测；全部预测保存后才统一评分。

| 新来源隔离IID测试条件 | EC F1（%） | EV F1（%） |
|---|---:|---:|
| 强空库 | 64.48 | 55.88 |
| ACE共用接口 | 66.59 | 66.92 |
| 主方法自身B1冻结库 | 83.51 | 84.25 |
| C1严格准入策略 | 80.29 | 89.01 |
| C2教师显式执行证据移除 | 86.98 | 80.38 |
| 第8次主方法终库 | 95.46 | 87.90 |

主方法相对强空库提升30.98/32.02个百分点；相对自身B1的EC提升11.95点，
预定同时校正区间为[7.33,16.60]。C2比较在EC/EV均支持显式执行证据的作用。
C1比较支持EC上的策略收益，不声称EV最高或所有消融全面胜出。
EV相对自身B1的3.65点估计尚未得到同时校正显著性支持，原结果完整保留。
这些是原生F1，不是整案准确率，也不是官方Advanced/OOD成绩。

## 3. 实际技能进化与论文机制证据

终库7条记录、14个任务执行块、3993 tokenizer tokens；B1为7条记录、13块。
16次教学中9次提交，EC 5次、EV 4次。B1之后主要是既有内容修订：
16项既有任务投影修订及1项新增EV投影，不用技能条数单调增长代替学习证据。
全部112个后续训练源均纳入同案B1比较，实际下发请求已核验；
EC/EV首答均值相对B1提高10.96/3.42点，测试终库全程冻结。

原16门槛的固定输出核对显示，主方法9次实际提交也都能通过严格门槛；
因此C1差异解释为准入/选择策略及其学习路径的整体对照，不能归因于单个计数否决。
C2仍有训练标签、事实、法条和控制器重放，不写成无标签或全无反馈消融。
旧版本整库/分量提交粒度消融在旧测试上完成并保留，不与本次不同案件混表。

## 4. 交付核验与完整目标的证据索引

以下路径均位于 `artifacts/research/openexempt_legal_scope_20261020/`，除另行标明者：

- 全2560真实任务投影、生成设置、原指标及18预定端点：`Utility_v6_actual_new_source_isolated_frozen_all10_all2560_original_metrics_18endpoints_dual_audit_20261031.json`（7933c50c）。
- 主方法全8批、16教师、原门槛、技能与成本：`Complete_output_utility_v6_complete8_all128_all16_gates_actual_teacher_gold_skill_evolution_native_costs_not_TEST_20261030.json`（bdf93a02）。
- 后续112源真实技能下发与执行：`Utility_v6_main8_all112_actual_postB1_skill_exposure_both_HTTPs_224pairs_scope_and_revision_timing_not_TEST_20261030.json`（ebe91485）。
- 已闭合的TRAIN教师支持及数值选择核对：`Utility_v6_all32_TRAIN_teacher_diagnosis_edit_support_actual_parent_correctness_no_new_calls_not_TEST_20261031.json`（9d6dadcc）、`Utility_v6_all48_original_adaptive_choices_float_min_same_coordinate_no_selection_change_no_calls_not_TEST_20261031.json`（17c5b1f2）。
- 两稿全部主表、伴随指标、18区间及不变方法节：`Utility_v6_bilingual_completed_frozen_results_claims_tables_methods_QA_20261101.json`（aac87c1e）。
- 最新导出文档与全部34页完整性/实际视觉核验：v09目录下 `visual_review_complete.json`（cf935885）。v07为早期导出，v08为保留的排版失败记录，均不冒充最新交付。
- 原v0.23论文、原八批、两粒度消融、原冻结TEST的1950原生输出及其输入、两盘归档和源码bundle保留：`Utility_v6_final_handoff_original_v023_initial8_TEST_original8_TRAIN_granularity_and_source_backups_preserved_20261101.json`（1ca4356c）。
- 最新稿件与交付文件的补充双盘备份收据：`Utility_v6_completed_English_primary_Chinese_auxiliary_paper_delivery_dual_status_20261101.json`；以该不可变收据的实际归档路径和哈希为准。

全部失败与不利结果保留，包括30次输出上限；未补答、未换成有利子集。
实验源码及旧研究未因写作而修改；复用原单实例冻结8B与已授权教师，
没有增加fallback、隐藏求解器、新付费服务或新模型部署。
新测试结果现已查看，未来若优化不得再把本批称为未见。

## 5. 本轮收尾边界

当前优化目标已有主方法收益、后续技能进化、必要机制控制和预绑定新隔离评价，
英文初稿可据此交付讨论；不因一项EV排序或不显著端点自动开启第9次训练。
额外main/ACE/Text独立构建继续按用户决定暂缓，不虚报独立学习方差。
旧结果与原主方法身份保留，不把简单控制事后改名为主方法。
下一阶段是用户审阅英文主稿和确定目标期刊，不自行投稿或启动新实验。
