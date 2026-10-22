# 论文工作入口

当前为v0.10内部审阅稿，尚不是投稿终稿。20页包含中英双语正文和实验附录D，
不代表英文投稿版有20页；期刊模板、作者信息和正式中英文分版仍待确定。

- [双语内部审阅PDF](../artifacts/research/manuscript_review_20261023/v010_bilingual_internal_v03/legal_skill_evolution_v010_bilingual_internal_review.pdf)
- [双语正文源稿](manuscript_v1_20261021.md)
- [实验附录D](appendix_experimental_details_20261022.md)
- [当前证据与剩余工作](evidence_and_completion_20261020.md)
- [PDF源文件、全部文本及图表核对](../artifacts/research/manuscript_review_20261023/v010_bilingual_internal_v03/final_review_QA_20261023.json)

PDF保留全部原稿内容、6张表、既有训练曲线和方法图，待填结果用黄色标记。
330个正文、标题和表格单元经实际PDF文本核对，差异为零；关键页面已检查。
源稿中的八批TRAIN结果没有改写成TEST结果，也未新增成绩、方法或实验臂。
本次使用已有系统字体和排版工具，不安装依赖，不改训练环境；完整源稿快照及
重现程序保存在PDF的渲染清单中，旧稿和旧渲染版本保留。

目前完整主方法TRAIN已完成，成熟经验方法与静态库对照、独立学习重复、机制
消融、真实末库完整矩阵、冻结TEST及最终统计仍须完成。若成熟TRAIN比较表明
方法不足，继续根因优化并用新Run ID重训，不用TEST反复调参。最新执行状态见
[项目执行入口](../docs/CURRENT_GOAL.md)。
