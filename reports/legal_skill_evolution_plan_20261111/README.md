# 法律技能进化方案包（2026-11-11）

**从[PLAN.md](PLAN.md)开始。** 冻结执行模型，教师更新外部技能库；两项研究方法为耦合法源前提提升、法律技能共同修订学习。该路线替代旧参数学习主线，历史成果保留。本包发布不恢复服务器。

- [机器协议](protocol.json)；[下一阶段Goal](SERVER_GOAL.md)
- [方法一](METHOD_ACQUISITION.md)及[查新](ACQUISITION_PRIOR_ART.md)
- [方法二](METHOD_EVOLUTION.md)及[查新](EVOLUTION_PRIOR_ART.md)
- [五库数据方案](DATA_PLAN.md)、[来源清单](candidate_source_manifest.json)、[20来源小试清单](pilot_source_manifest.json)
- [受控机制层](CONTROLLED_LAYER.md)及[逐来源证据](CONTROLLED_LAYER_EVIDENCE.json)
- [一致性检查](PACKET_CHECK.json)、[基础机制检查](LEARNING_OBJECTS_CHECK.json)、[审查处理](qa_logs/RESOLUTION.md)

离线复现（Python标准库，无模型调用）：

```bash
python check_premise_lifting.py
python check_joint_revision.py
python check_learning_objects.py
python check_packet.py
```

脚本中的精确读取fixture和构造规则用于验证算法行为，不是执行模型实测，也不是原生数据成绩。原始数据审查依据、上游固定版本、内容hash和许可见DATA_EVIDENCE.json。数据清单已分组，但旧TEST的实际暴露资格仍须服务器历史核对。

候选来源清单与pilot的sha256字段按移除sha256字段后的排序紧凑JSON计算；SHA256SUMS记录各文件的实际字节hash，两者用途不同。
