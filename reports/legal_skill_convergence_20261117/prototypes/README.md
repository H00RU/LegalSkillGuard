# 确定性原型

全部零模型调用，仅用已有 TRAIN 来源。示例不是模型准确率实验。

在本目录运行：

```text
python prototype_m1.py
python airline_real_relation.py
python airline_partial_relation.py
python legal_distinguishing_pairs.py
```

需要 numpy、pandas。自带 RuleArena 原生计算依赖闭包与 MIT 许可；原来源与每个输入的哈希见 airline_real_relation_fixture.json。使用既有审核/原生函数不等于自动完成英语法律理解。

- prototype_m1：有限事件世界的关系编码与消费者保持。
- airline_real_relation：真实 TRAIN 来源，自动阈值/分组候选与原生回放。复杂度成本是示例，不是弱读者测量。
- airline_partial_relation：自动源编辑、共享剩余语义下的总价差关系及原生校验。遮蔽基础费用标注是受控诊断，原文仍含票价。
- legal_distinguishing_pairs：多解释、依赖与作用域检查；SARA原句真实，但示例阈值与所有权规则为合成机制，不是SARA金标。

现有结果JSON保留运行记录。生产实现需完成实际弱模型读取、跨来源学习及同信息强对照。

原生计算代码仅清理行尾空白；原下载哈希保存在来源fixture，实际打包文件哈希见顶层MANIFEST.json。评分逻辑未改。
