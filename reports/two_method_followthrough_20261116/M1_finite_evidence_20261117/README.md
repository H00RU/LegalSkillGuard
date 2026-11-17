# M1 固定有限验证补充包

结论与数字见上一级 [M1_FEASIBILITY_DECISION_20261117.md](../M1_FEASIBILITY_DECISION_20261117.md)。这是原3个TRAIN来源的有限可行性核验，不是完整训练或盲测。M2停止，当前M1版本停止扩展；整Goal未完成。

先按第一包安装依赖，再运行两条离线命令：

```bash
.venv/bin/python -m experiments.m1_replay_evidence
.venv/bin/python -m experiments.m1_replay_feasibility
```

第二条复用18份原真实响应和2份新增普通提示响应，核验同链参考、解码、原生评分、开发选择和固定F与自动F′的差异。没有模型客户端或网络调用。第一条会在缺少原F库时验证哈希并解压所需的同一冻结库；不覆盖已有文件。

`finite_replay.json.gz`包含原始源输入、接口/参考对应关系、20次原请求及响应、2次新增预测、TRAIN D/C原生评分注释、冻结选择、14条原生评分和归因补全证据。`protocol.json`记录生成前锁定的预算与范围，`ledger_index.json`提供连续账本ID/状态/请求和结果hash；不是整库账本。`terminal.json`保留按原生分数计算的初步信号，最终`attribution_decision.json`进一步指出正分输出对既有源审unknown的断言，因此决定停止当前版本扩展；二者保留完整核验过程。

`automatic_generation_audit.json`列出实际F导出的端口变化；`same_chain_classification.json`区分输入/消费者不确定、解码拒绝与可执行案例。代码：`experiments/m1_finite_feasibility.py`为实际有限调用driver，`m1_feasibility_attribution.py`为归因复核，`m1_replay_feasibility.py`为本包独立离线入口。原driver依赖本地连续账本和原封存资产，不能在新检出中重建空账本或重发已有效的请求来声称复现。

新增实际调用2次、5576 tokens，GPU费用未计价；原18次历史支出保留在原账本，没有计为零或本轮新增。模型参数未训练，未读取DEV/TEST用于修复；原曝光事实不重置。仅上传必要证据，不含凭据或整套历史缓存。
