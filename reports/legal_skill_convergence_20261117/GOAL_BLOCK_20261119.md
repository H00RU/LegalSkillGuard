# LegalSkillGuard Goal Block

现行方案 revision 5，2026 年 11 月 19 日。原研究 Goal 已标记为 `blocked`。连续三次核对均未找到有源文和 TRAIN 实测支持、能与同信息强对照产生可归因原生差异的新候选。M1 和 M2 的独立原生收益仍待验收。 [现行方案](PLAN.md) · [接续协议](continuation_protocol_20261119.json)

## 已交付

- 128 个来源、8 批训练，五库冻结 TEST、分库指标、独立消融及强对照。原冻结协议、结果、源码快照及曝光记录均通过完整性核验。 [冻结 TEST 原生结果](paper/tables/TEST_B8_NATIVE_TABLES.md) · [机制审计](paper/tables/TEST_B8_MECHANISM_AUDIT.json)
- 论文初稿与 revision 5 五库累计正式 B8 DEV。该开发评估复用 80 个母来源及五臂 1,920 个原生预测。共享来源规则改善了五库的多项原生指标，四组 M1/M2 消融在各库的原生输出逐项一致。 [累计 DEV 数据表](paper/tables/REVISION5_CUMULATIVE_FORMAL_DEV_20261119.json) · [论文初稿](paper/METHODS_AND_DEVELOPMENT_RESULTS.md)

## 阻断依据

- **M1，消费者约束的关系接口学习。** 两个启用臂在 Diversity 各调用关系接口 16 次，同源字面强对照与合成接口均答对 16 题。宾州 OpenExempt 合并形态后，关系接口的分类和估值 F1 分别较固定字段低 5.12 和 4.29 个百分点。 [Diversity 同信息配对](paper/tables/REVISION5_M1_DIVERSITY_DEV_LITERAL_20261119.json) · [OpenExempt 跨任务配对](paper/tables/REVISION5_OE_PAIRED_FORMS_20261119.json)
- **M2，共享语义约束的对照监督合成。** OpenExempt 资产绑定修正后，B7 回放里的共享筛选和同信息直接核对同步改变候选选择。35 组已存真实投影中，二元与联合筛选决策一致。正式 B8 两组 M2 消融的最终程序在五库分别一致。 [B7 选择回放](paper/tables/REVISION5_OE_EC_BINDING_20261119.json) · [真实投影审计](paper/tables/REVISION5_M2_CUMULATIVE_AUDIT_20261119.json)

阻断核验新增模型请求 0，连续账本 14,716 笔，含 14,680 笔完成、36 笔失败，在途 0。恢复依据是新的源文和 TRAIN 证据支持一项能区分强对照的候选，或明确修改验证范围。 [当前交接](../../docs/NEW_CHAT_HANDOFF.md)
