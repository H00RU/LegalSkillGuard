# 论文工作入口

当前为v0.11内部审阅稿，尚不是投稿终稿。20页包含中英双语正文和实验附录D，
不代表英文投稿版有20页；期刊模板、作者信息和正式中英文分版仍待确定。

- [最新双语内部审阅PDF](../artifacts/research/manuscript_review_20261023/v011_bilingual_internal_v01/legal_skill_evolution_v011_bilingual_internal_review.pdf)
- [双语正文源稿](manuscript_v1_20261021.md)
- [实验附录D](appendix_experimental_details_20261022.md)
- [当前证据与剩余工作](evidence_and_completion_20261020.md)
- [PDF源文件、全部文本及图表核对](../artifacts/research/manuscript_review_20261023/v011_bilingual_internal_v01/final_review_QA_20261023.json)
- [上一版v0.10审阅PDF](../artifacts/research/manuscript_review_20261023/v010_bilingual_internal_v03/legal_skill_evolution_v010_bilingual_internal_review.pdf)

v0.11将早期B2检查点表替换为同128来源的完整八批首答对照：主方法EC/EV F1
82.03/79.16%，ACE任务适配61.87/53.85%，强直接空库60.17/62.92%。单次seed45
学习流、失败计零，不是最终库或TEST成绩；原主方法八批曲线与46个点不改。
PDF完整保留当前源稿的6张表、既有训练曲线和方法图，待填结果用黄色标记。
333个正文、标题和表格单元经实际PDF文本核对，差异为零；第1/12/13/18页已查看。
旧v0.10正文与附录D逐字快照、原PDF保留，没有变更实验方法或增添实验臂。
本次使用已有系统字体和排版工具，不安装依赖，不改训练环境；完整源稿快照及
重现程序保存在PDF的渲染清单中，旧稿和旧渲染版本保留。

目前完整主方法TRAIN已完成，成熟经验方法与静态库对照、独立学习重复、机制
消融、真实末库完整矩阵、冻结TEST及最终统计仍须完成。若成熟TRAIN比较表明
方法不足，继续根因优化并用新Run ID重训，不用TEST反复调参。最新执行状态见
[项目执行入口](../docs/CURRENT_GOAL.md)。
