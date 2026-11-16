# 可交接包

先读 [PLAN.md](PLAN.md)。这是根据Idea Evaluator补齐的执行版，替代旧候选指令；历史方案与结果保留。两项均为Accept with Revisions，尚无真实模型效果证据。

|内容|文件|当前状态|
|---|---|---|
|统一方案与固定阶段|PLAN.md、protocol.json|已写明实现、数据、对照、训练测试与停止扩展条件|
|查新与评估|RELATED_WORK.md、IDEA_EVALUATION.md|当前两项差异、主要缺口和投入判断|
|十篇文献历史核查|LITERATURE_REVIEW_HISTORY.md|背景证据，其中旧候选已由PLAN替代|
|第一方法及近邻差异|INTERFACE_METHOD.md|残差引导成对接口学习，承接1115，不是已否定判别提示|
|第一项有限核心|interface_prototype/|11项确定性检查通过；尚无自然语言接口学习|
|第二项经验核心|prototype/|8项检查通过；附条件模型，不是实测提升|
|真实TRAIN审计|data_audit/|可复现计数、输入hash、1份真实部分图对；无完整版本图对|
|替代思路查新|REPLACEMENT_RESEARCH.md|跨源绑定归纳被降级，不是本包实施路线|
|待发送交接|SERVER_HANDOFF.md|未发、未恢复服务器|

运行离线检查：在 interface_prototype 目录运行 python -m unittest -v；在 prototype 目录运行 python test_channel.py（需numpy/scipy）。数据审计脚本依赖现有本地档案路径；服务器应先对应其实际文件，不能把路径不存在理解为数据不存在。

本包0研究模型调用。11+8测试数仅说明离线代码检查，不说明论文创新强度或基准涨分。data_audit的来源材料限定既有TRAIN；旧TEST暴露信息来自历史报告，没有重新运行TEST。
