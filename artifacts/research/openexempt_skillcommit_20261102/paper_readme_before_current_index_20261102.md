# 论文初稿入口

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
