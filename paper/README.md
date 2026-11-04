# 当前论文、代码与实验材料入口

更新：2026-11-04。英文为投稿主稿，中文为独立辅助稿。动态实验状态以
[CURRENT_GOAL](../docs/CURRENT_GOAL.md)为准；本页不把正在运行的比较写成已完成结果。
当前论文对应已完成的时间顺序学习、原来源隔离比较及SkillCommit补充，与保留的v0.23
研究分开；独立学习重复仍暂缓。版本/审阅状态放在本入口，正式正文不再附内部审阅标语。

## 当前稿件

- 英文：[Markdown](utility_skill_manuscript_working_20261030.md)、
  [Word v15](../artifacts/research/manuscript_review_20261030/utility_v6_skillcommit_author_year_v15_20261104/utility_v6_working_en.docx)、
  [PDF v15](../artifacts/research/manuscript_review_20261030/utility_v6_skillcommit_author_year_v15_20261104/utility_v6_working_en.pdf)。
- 中文：[Markdown](sections-zh/utility_skill_manuscript_working_20261030.md)、
  [Word v15](../artifacts/research/manuscript_review_20261030/utility_v6_skillcommit_author_year_v15_20261104/utility_v6_working_zh.docx)、
  [PDF v15](../artifacts/research/manuscript_review_20261030/utility_v6_skillcommit_author_year_v15_20261104/utility_v6_working_zh.pdf)。
- [参考文献](utility_skill_references_20261030.bib)、
  [v15导出与关键页面实看核验](../artifacts/research/openexempt_skillcommit_20261102/run05_bilingual_v15_complete_output_validation_20261104.json)、
  [导出源和文件hash清单](../artifacts/research/manuscript_review_20261030/utility_v6_skillcommit_author_year_v15_20261104/render_manifest.json)。
- [英文投稿配套材料](submission_materials_en_20261104.md)：与主稿一致的纯文本标题/摘要、关键词、
  四条亮点、投稿信草稿及声明事实。目标期刊和作者字段待确认，不是已经发送的投稿信。
- [2026-11-04论文质量审查](../docs/reports/PAPER_QUALITY_REVIEW_20261104.md)：原始响应、分数、区间、图表及论证核验，含10项中英文改句建议；
  [完整复算证据](../artifacts/research/openexempt_skillcommit_20261102/manuscript_quality_review_readonly_reproduction_20261104.json)。
  审查建议尚未写回主稿，当前可下载的论文仍是下面所述的v15，不能把审查报告当成修改后的新论文。
- 当前v15英文22页、中文20页，各13张表、23个原生数学对象、2张原图、11条参考，正文为作者—年份引用。
  两语稿已补入SkillCommit完整构建、冻结TEST质量、实际下发与成本，原十条件分数不变；
  另以LegalBench、Factoring Statutory Reasoning及2026年JustifIT-QA补足法律任务定位，
  新增三条均在两语正文引用，不作为新增实验条件。全文文字、数学及嵌图通过导出核验，
  另实看英文7页、中文6页的首页、主表、补充区间、构建/推理成本、参考与构建条件表。
  这是自由格式可审阅稿，尚未填作者页或适配选定期刊模板，不冒称已经投稿。
  这些是本工作区实际文件链接，不在未实查远程仓库前宣称已经公开发布。
- 旧版保留：[v11](../artifacts/research/manuscript_review_20261030/utility_v6_bilingual_evidence_update_v11_20261102/render_manifest.json)、
  [v12及生成条件核验](../artifacts/research/manuscript_review_20261030/utility_v6_bilingual_conditions_update_v12_20261102/evidence_update_validation.json)、
  [v13完整补充初导出](../artifacts/research/manuscript_review_20261030/utility_v6_skillcommit_complete_supplement_v13_20261104/render_manifest.json)、
  [v14清理审阅标语版](../artifacts/research/manuscript_review_20261030/utility_v6_skillcommit_clean_manuscript_v14_20261104/render_manifest.json)。
  v12不含后来SkillCommit成绩；v13保留完整整合源稿，v14/v15只清理开头工作状态段并改善引用/排版，科学正文不变。

## 当前论文研究与代码

任务是OpenExempt法定豁免分类EC和金额估值EV；执行器Qwen3-8B权重固定。
主方法为任务专注的执行证据教学与完整输出效用发布。多轮客户咨询、ContractNLI和
v0.23属于保留历史，不是当前论文的任务或默认复现入口。

| 用途 | 入口与版本 |
|---|---|
| 第8次完整主方法 | [配置](../configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json)、[379文件源绑定](../configs/openexempt_complete_output_utility_public_assets128_20261030_run01.frozen.json)、[实现](../experiments/openexempt_online.py) |
| 原十条件冻结评价 | [实际矩阵配置](../artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json)、[原协议](../docs/research/OPENEXEMPT_V6_FINAL_SOURCE_ISOLATED_FROZEN_EVALUATION_20261030.md)、[实现](../experiments/openexempt_frozen_eval.py) |
| 当前补充SkillCommit对照 | [run05配置](../configs/openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05.json)、[648文件源绑定](../configs/openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05.frozen.json)、[完整协议](../docs/research/OPENEXEMPT_SKILLCOMMIT_VERIFIED_REFERENCE_ENGLISH_PROTOCOL_20261102.md)、[实现](../experiments/openexempt_skillcommit.py) |
| 主方法技能表示与编辑 | [任务投影和组合](../legal_skill_guard/learning/task_scoped_skills.py)、[发布操作](../legal_skill_guard/learning/publication.py) |
| 原任务、数据与评分 | [OpenExempt接口](../legal_skill_guard/openexempt.py)、[公共标签双射](../legal_skill_guard/learning/legal_namespace.py) |
| SkillCommit独立原语 | [修补/检索/行为分组等](../legal_skill_guard/learning/skillcommit.py)；不是主方法准入 |

## 已完成证据与当前缺项

- [原冻结主表和配对区间](tables/utility_frozen_results_20261101.json)、
  [加入SkillCommit的11条件呈现表及独立两端点补充](tables/utility_frozen_results_with_skillcommit_20261104.json)、
  [实际技能进化/构建成本](tables/utility_training_evolution_cost_20261030.json)、
  [冻结推理成本](tables/utility_frozen_inference_cost_20261102.json)、
  [实际执行案例](tables/utility_frozen_case_study_20261102.json)。
- [原2560条逐案结果](../runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json)、
  [完整主方法及控制交付索引](../docs/reports/UTILITY_V6_PAPER_HANDOFF_20261101.md)。
- [贡献—证据与后续比较路线](../docs/research/PAPER_CONTRIBUTION_EVIDENCE_PLAN_20261102.md)、
  [投稿材料与作者待确认项](../docs/research/PAPER_SUBMISSION_PREPARATION_20261102.md)、
  [英文复现说明](../docs/research/PAPER_REPRODUCTION_GUIDE_20261102.md)、
  [完整Goal交付审计与尚需确认的信息](../docs/reports/GOAL_DELIVERY_AUDIT_20261104.md)。
- 主方法、必要控制与原十条件冻结评价已完成；SkillCommit于11月4日01:18完成八批构建，
  实际终库含21条高层模式和23条残余补丁，03:31完成既有TEST128案/256任务冻结评价。
  [完整构建及B8证据](../artifacts/research/openexempt_skillcommit_20261102/run05_eighth_complete_batch_and_build_evidence_20261104.json)
  记录2,015次构建8B生成与930次成功教师响应；测试另有256次生成、0教师调用。
  [完整测试核验](../artifacts/research/openexempt_skillcommit_20261102/run05_complete_frozen_TEST_scores_delivery_cost_and_pairing_20261104.json)
  逐项复算全部评分与固定两端点区间，保留七份封顶零分和实际检索集中现象。
  额外独立学习重复保持暂缓，当前不宣称论文已经投稿。

## 核对入口与复现约定

从项目根目录查看实际入口，不运行历史默认CLI：

```bash
.venv/bin/python -m experiments.openexempt_online --help
.venv/bin/python -m experiments.openexempt_frozen_eval --help
.venv/bin/python -m experiments.openexempt_skillcommit --help
```

封存Run ID、配置和frozen清单共同标识当次实验。独立复现须使用新Run ID/配置、
对应源版本与新机器实际环境捕获，保留原模型、数据、公开接口及解码条件，再冻结和运行。
不要覆盖已有运行或把不同源版本当作同配置重复。已有预测、标签和原评分可单独核算；
新模型调用不是核算原分数的前提。英文复现说明已给出全2560份离线评分命令、实测
双环境、原入口及独立重跑所需状态；原评分复现已通过，完整新机器学习/推理复现尚未
完成。最终公共发布地址和作者批准在比较完成后统一核验；本索引不冒充已经完成的
公开代码发布。

## 历史：2026-10-26 v0.23原入口

以下内容按原日期保留；其中当时的等待指示、旧任务和旧成绩不是当前执行状态。

### v0.23论文初稿入口

研究已由用户于2026-10-26重新开启主方法优化Goal，见[当前研究状态](../docs/CURRENT_GOAL.md)。
本目录v0.23和对应PDF保留为原完整实验的老师审阅初稿，不含尚在开发的新方法成绩；
下文“交付后等待”描述的是上一轮交付指示，不覆盖最新优化授权。

当前为2026-10-26的v0.23老师审阅初稿，正文和实验附录已整合完整冻结TEST结果。
审阅PDF共33页，包含中英双语、14张表、方法图和训练曲线；不是33页英文投稿稿。
期刊模板、作者信息、代码/数据发布权限和正式中英文分版仍待确定。

- [老师审阅PDF v0.23](../artifacts/research/manuscript_review_20261026/v023_bilingual_teacher_review_v01/legal_skill_evolution_v023_bilingual_teacher_review.pdf)
- [双语正文源稿](manuscript_v1_20261021.md)
- [实验附录D](appendix_experimental_details_20261022.md)
- [PDF文本、表格及关键页面核对](../artifacts/research/manuscript_review_20261026/v023_bilingual_teacher_review_v01/final_review_QA_20261026.json)
- [完整TEST结果与来源/成本审计](../artifacts/research/openexempt_legal_scope_20261020/Initial8_TEST_complete2048_1950native_prespecified14contrasts_gate_recompute_conditional_singlebuild_20261026.json)
- [论文证据与历史记录](evidence_and_completion_20261020.md)

首轮必要实验已完成：主方法八批、ACE八批、Text128案离线构建、盲静态对照、
整库和任务级两项八批消融，以及128隔离来源、八条件共2048逻辑预测的冻结测试。
主方法TEST EC/EV原F1为87.43%/86.18%，强空库64.08%/61.88%；
这些不是分类准确率或法律正确性认证。相较自身B1，EV提高13.92个百分点有来源条件证据，
EC的0.98个百分点不确定；两个简单控制EC更高，主方法EV优势的次要校正区间均含零。
正文不宣称细粒度机制全面领先，不据TEST换主库、改阈值或挑有利样本。

主方法、ACE、Text的独立学习重复仍按用户决定暂缓，未自动启动。
当前区间条件于各一份实际学习库，不估计跨学习随机性；首轮完成不等于全部论文实验完成。
原TRAIN首答、末库拟合、所有无效输出及退化均保留，未把训练重放填入TEST主表。

已按师兄paper-ideation、paper-experiments-appendix、paper-figures-data组织问题—证据、
主表和附录，并用Nature skill检查表述边界。没有因模板要求编造重复、误差带或创新点。
本次交付后按用户要求等待回复，不再自动启动实验或继续修订。

历史版本保留于Git及双盘档案。[v0.16内部预览](../artifacts/research/manuscript_review_20261024/v016_bilingual_internal_v01/legal_skill_evolution_v016_bilingual_internal_review.pdf)
不是当前稿件；运行时方法、模型、数据、技能库、评分和统计规则本次均未改变。
