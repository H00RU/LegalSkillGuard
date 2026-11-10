# 已执行的检查及复现

所有检查均在2026-11-10本地执行，模型调用0，服务器训练未启动。

| 检查 | 实际结果 |
|---|---|
| 数据manifest | 448条，256/64/128；98个临时法源家族不跨集；每族≤16；item/全文/target哈希各448互异 |
| M1监督存在性 | 256 TRAIN中109来源有共享非主体内容；47有同文本多角色；跨单元角色新增10来源/13次 |
| M2例子 | 三条件八种赋值通过 |
| M2定向交互公式 | 16种赋值×4个gold选择，共64次恒等式检查通过 |
| M2原生监督存在性 | 在256 TRAIN的有限搜索中，29来源找到同节点、四张合法图的非零交互见证 |

M1中的同文字共享指载荷存储，不证明它们是同一法律谓词。M2中的布尔见证是条件结构的抽象激活，不是新法律案件标签。上述计数说明训练目标可从现成数据得到，不表示方法取得29或47条正确预测。

原始数据下载地址及SHA256见protocol.json。下载后在本目录执行：

```sh
python probe_shared_fragments.py --data /path/to/normbench_v1.json --output shared_fragment_reproduced.json
python probe_native_interactions.py --data /path/to/normbench_v1.json --manifest data_manifest/normbench_candidate_split_v1.json --output interaction_reproduced.json
python verify_method2_example.py
python verify_method2_scope_interaction.py
sha256sum -c SHA256SUMS.txt
```

两个计数脚本只使用manifest的TRAIN。M2探针每分支最多16四格、每四格最多64赋值；未发现见证不作无交互判断。固定搜索并不替代正式组合器训练。

本包未声称已经完成法源官方ID人工核验、独立测试审校、Catala16版本配对或新的SARA外测。这些状态在数据报告中单列；首轮训练所需自动检查和现成gold已经可用。
