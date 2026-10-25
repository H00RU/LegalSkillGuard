# 论文工作入口

当前正文/附录源码为v0.22，保留完整消融、TRAIN分阶段指标及真实资源，并收口引言的最近邻方法区别；保留的PDF仍是v0.16内部预览，
尚不是完成版老师初稿或投稿终稿。23页包含中英
双语正文和实验附录D，不代表英文投稿版有23页；期刊模板、作者信息和正式
中英文分版仍待确定。必要实验及实际结果整合完成后再交付老师审阅稿。

- [保留的v0.16双语内部排版预览（当前源码已到v0.22，整篇PDF尚未更新）](../artifacts/research/manuscript_review_20261024/v016_bilingual_internal_v01/legal_skill_evolution_v016_bilingual_internal_review.pdf)
- [双语正文源稿](manuscript_v1_20261021.md)
- [实验附录D](appendix_experimental_details_20261022.md)
- [当前证据与剩余工作](evidence_and_completion_20261020.md)
- [PDF源文件、全部文本及图表核对](../artifacts/research/manuscript_review_20261024/v016_bilingual_internal_v01/final_review_QA_20261024.json)
- [保留的v0.13内部审阅PDF](../artifacts/research/manuscript_review_20261023/v013_bilingual_internal_v01/legal_skill_evolution_v013_bilingual_internal_review.pdf)
- [三种提交粒度的八批首答与同案B1差值副图（单次学习，不含TEST）](figures/granularity_prequential_caption_20261025.md)

主方法八批、ACE八批、Text128案离线构建及静态TRAIN控制已完成。正文分别
报告在线首答和末库TRAIN拟合，不把两阶段混比。完整八批首答中主方法EC/EV
F1为82.03/79.16%，ACE任务适配61.87/53.85%，强直接空库60.17/62.92%；
不是最终库或TEST成绩。Text末库TRAIN拟合52.74/49.73%的不利结果也保留。

当前协议保留八条件：六行主表及Whole-bank/Task-local两项粒度消融。两项替代消融
统一使用四并发新Run ID，从空库开始；原串行整库部分结果及成本完整保留。
新Whole-bank和Task-local均已完整八批结束，末库分别六条/2615及六条/2435tokens，
全部末库及实际运行已双盘保全。共同八条件冻结TEST于25日23:31 CST启动，正在保存预测，
全部逻辑预测保存后才评分；这不等于TEST成绩已完成。全部主方法、
ACE和Text独立学习重复暂缓至必要实验和老师初稿后的用户决定，不会自动启动。

三种粒度的完整首答与末库TRAIN拟合已在附录D.9分列；主方法并非各阶段、各端点都领先。
任务级B7/B8均未更新库，分数反弹不写成当批学习成功。附录D1记录两项控制的完整成本，
不以精确请求复用扩充物理调用，不以墙钟时间冒充GPU忙时或因果提速。

保留的v0.16预览包含当时正文、附录、8张表、既有训练曲线和方法图；404个实际PDF文本
单元核对差异为零，第1/13/14/19/21页已查看。未完成结果用待填标记区分，
独立重复另标暂缓。附录资源表记录实际调用与已知token，不声称等总计算，
ACE一次超时用量未知仍保留为下界。完整源快照及复用排版程序在渲染清单中，
未填入未完成成绩。当前源码保留执行差异、反馈判定缺陷及语义诊断的证据边界，
未将训练曲线写入TEST表，也未把暂缓的独立重复写成完成；
当前不重新渲染PDF，待必要实验结果整合后交付老师审阅稿。

最新实际执行状态见[冻结测试元数据进度](../runs/legal_openexempt_initial8_frozen_TEST_20261025_run01/progress.json)及[项目执行入口](../docs/CURRENT_GOAL.md)。研究侧只查看进程、计数和配置，不检查未完成TEST的内容或分数。冻结TEST不向教师
提供反馈，不用于挑选库或修改后续同算法重复；任何科学修订须单独标明研究版本。
