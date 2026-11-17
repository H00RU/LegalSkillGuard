# 法律技能进化：收敛后的两项方法

> **2026-11-18 已补齐跨库实施及主动优化要求（revision 3）。** 当前正式五库为OE、ContractNLI、MAUD、Airline、LegalBench Diversity。执行以[PLAN](PLAN.md)、[跨库实施](CROSS_DATASET_IMPLEMENTATION.md)、[数据选择](DATA_SELECTION.md)、[配置](protocol.json)与[新Goal](SERVER_GOAL.md)为准。单库低分不触发停止；允许最多3轮成体系的TRAIN/DEV优化后冻结验证。实验交付齐全不自动代表Goal达成，两方法仍须有实际贡献证据。

**推荐投入：法律消费者约束的关系接口学习；共享语义约束的对照监督合成。**

执行模型保持冻结，教师与外部技能库保留。第一项让模型更容易正确使用已有法律技能；第二项从不完整语义标注中构造可信训练关系，减少错误经验被写入技能库。两项有独立学习对象、独立消融与真实原生任务的收益路径。

本包按用户最新核心代码提交 [354bece66](https://github.com/H00RU/LegalSkillGuard/tree/354bece66fd9a0b1e7bc8dab1a6d7159ee141345) 核验。它替代旧执行方案中尚待进行的方法选择和旧风险通道M2；历史实验、负结果、账本与暴露记录不撤销。

- [统一方案与固定验证](PLAN.md)
- [第一项算法与扩展查新](METHOD_1.md)
- [第二项算法与语义作用域](METHOD_2.md)
- [综合查新及评估后再次排重](RELATED_WORK.md)
- [idea-evaluator复审](IDEA_EVALUATION.md)
- [最新核心代码审计与复用边界](CURRENT_CODE_AUDIT.md)
- [配置](protocol.json)
- [服务器Goal](SERVER_GOAL.md)
- [可复算原型](prototypes/README.md)与[运行检查](CHECKS.json)

复审结论为 **Accept with Revisions：按本包已具体落实的修订范围值得投入**。并非港科大机构/专家背书，也不是用评分证明效果。本轮没有调用模型或恢复服务器。

已完成的机制证据：有限关系接口合成；一个真实Airline TRAIN来源的合成/原生结果均为1433；自动生成合法源变化与费用差关系-70，原生复核为1433→1363；多解释、未知事实共享范围与不可能终答归因的检查。原型结果不等于新模型准确率。

锁定两项机制及强对照，后续围绕它们完成生产实现、固定真实比较、完整训练与分库测试；不因某个通用组件已有文献就重开选题。未找到相同完整对象的直接重复实现，不写“全球无人做过”。
