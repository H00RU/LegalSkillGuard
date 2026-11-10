# 当前Goal统一补齐包

**当前执行入口：[统一方案](PLAN.md) + [机器配置](protocol.json) + [补充指令](HANDOFF.md)。**

本包接续正在执行的Goal，替换2026-11-10旧单库方案的数据范围、M1核心目标和对照矩阵。M2及可复用实现保留。当前完成线是五库256来源完整混合训练与七系统分库DEV评估；五库各32 TEST留待冻结后。

- [M1具体算法](M1_METHOD.md)、[查新和差异](NEW_PRIOR_ART.md)、[确定性更新检查](M1_FINITE_CHECK.json)
- [M2五库接入与代码迁移](M2_AND_MIGRATION.md)
- [数据与划分说明](DATA_PLAN.md)、[实际候选清单](mixed256_candidate_manifest.json)、[可用性审计](data_availability_audit.json)
- [证据与主张契约](RESEARCH_CANON.md)、[集成核验](PACKET_CHECK.json)、[文件哈希](SHA256SUMS.txt)

无需重新做已有效的NormBench四格代数验证；原文件继续见[此前已发布方法包](../legal_semantic_learning_20261110/README.md)。

本包自身可离线核验：

```bash
python check_m1_local_credit.py
python verify_packet.py
```

以上检查只验证代数、清单及协议一致性，不启动模型或服务器实验。真实适配、训练和DEV指标由当前服务器Goal交付。清单已经生成，最新服务器暴露仍须在锁定新运行配置时核对。
