# 语义消歧研究设计与查新补充（2026-11-09）

这是对**正在执行的服务器 goal**的补充，不要求重开、重置或暂停 goal，也不覆盖服务器研究分支的实现与实验记录。

先读：

1. [与服务器当前工作的衔接及避免重复清单](server_alignment.md)：发布前已读取研究分支c6277a7；两项真实模块生成、上限修复原型和已有查新直接复用。
2. [完整设计与强对照](research_design_review.md)：M1混淆对驱动的消歧技能编译；M2结构化误读通道学习。二者均为待真实验证的方法设计，不能声称创新已过关。
3. [最近邻查新记录](novelty_specialist.md)、[第二方法专项复核](structured_reader_error_review.md)、[被排除的分组纠错主张](group_robust_disambiguation_audit.md)。查新记录含被排除的中间方案，最终设计以主报告为准，不是同时推进多条路线。
4. [来源级失败与实现可行性](feasibility_specialist.md)、[统计结果](feasibility_source_audit.json)、[最终科学QA](final_review.md)。

本轮只补两项方法的最小真实TRAIN验证及同信息强对照，不启动新一轮完整建库、完整评测矩阵、正式TEST或论文写作。常规工作在既有资源授权内自主推进；不恢复旧100/2预算或按修复轮次逐次确认。

## 本地原型证据的正确用途

- [检查盲区及有限机制结果](mechanism_probe_results.json)
- [结构化误读通道有限结果](reader_channel_probe.json)
- [最新/历史检查函数一致性](latest_semantic_check_equivalence.json)

这些新增原型为0模型调用；人工构造标签、锚点、错误与历史真实响应明确分开，不能记作模型真实纠错或跨库成绩。

三个Python文件是原始审计脚本的归档，不是服务器生产入口，也不要求重跑：`mechanism_probe.py`、`feasibility_source_audit.py`依赖原审计目录中的历史快照和public TRAIN包，完整实验数据未随本次文档上传。`reader_channel_probe.py`仅为自包含的构造算法用例。已有等价复核可直接引用；必要时按实际保存路径复用脚本，不新建第二套运行框架。

效果诊断固定ced5c965，历史科学记录固定6c2f2a5，服务器发布前增量固定c6277a7。若服务器已有更晚进展，以真实代码、原始记录和当前授权为准，先做机制/证据映射再补缺失项。此目录不改变服务器goal状态。
