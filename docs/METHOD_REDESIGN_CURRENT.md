# 已有研究资产与证据索引：无当前研究队列

2026-11-16，旧Goal已clear。本文只保存接手所需事实；新方法及任务由新对话定义。交接前长进度文档已[逐字节归档](history/goal_cleared_20261116/entrypoints_before/docs/METHOD_REDESIGN_CURRENT.md)，其中的active、优先事项和“下一步”不再生效。

## 最应知道的结论

- **旧完整研究有真实整体收益，专门机制未获证实。** Full冻结TEST五库原生宏平均53.848%，对AllPorts＋CoRev为42.619%；但专门Lift提议、最终依赖端口、已学共同修订模式和跨库终端路径均为0，不能把臂名分差归因于这些机制。
- **后来的C＋观察契约没有证明两项独立优势。** 固定DEV ours46.884%、NoC/空库48.134%；与历史Full59.330%的DEV来自不同获取轨迹，不能互换为严格消融。
- **最后C的增量是TRAIN拟合，不是新泛化。** 原24合同/96视图C76、充分修复的普通教师75；两臂共享学习器各提高5题。同读数/同G的新增原文通道有8修正/0误改，但仍不足以证明整个C优于同信息强获取。
- **观察路径有真实执行恢复，强控制吸收了效果。** 最新原TRAIN冻结复用方法0/2、普通教师2/2、同方法契约普通读取1/2；角色关联、kind及部分聚合依赖仍有问题。
- 以上是具体实现与数据上的结论，不证明整个研究问题不可能；也不强制新任务继续修这些候选。

## 资产入口

|内容|位置与用途|
|---|---|
|参考工作、所有主要路线和避坑总结|[旧Goal精炼回顾](../reports/legal_skill_evolution_run_20261111/component_training_20261115/GOAL_RETROSPECTIVE_20261116.md)。先读它，按需追原始证据。|
|原完整固定研究|[阶段复核](../reports/legal_skill_evolution_run_20261111/FIXED_STUDY_STAGE_REVIEW.md)、[完整报告](../reports/legal_skill_evolution_run_20261111/README.md)。|
|最新C的真实学习、强对照和入口|[C结算报告](../reports/legal_skill_evolution_run_20261111/component_training_20261115/C_diagnostic_refinement/README.md)。|
|观察契约、读取职责和原生执行|[第二项复核](../reports/legal_skill_evolution_run_20261111/component_training_20261115/M2_responsibility_review/README.md)。|
|完整混合续训与DEV负结果|[固定DEV报告](../reports/legal_skill_evolution_run_20261111/component_training_20261115/README.md)。|
|实际实现|`legal_skill_guard/skill_evolution/`、`experiments/`、`configs/`、`tests/`；冻结复现用各run绑定快照，当前代码不是所有历史版本的替代。|
|原始结果与连续账本|`artifacts/legal_skill_evolution*`及`artifacts/rr_v2_preflight/research_ledger.sqlite3`。保留物理失败及重试。|
|旧Goal末尾未验证的草稿|`source_candidate_diagnosis.py`、`source_local_refinement.py`及`legal_skill_evolution_C_local_acquisition_20261116`。仅离线检查，教师任务未派发；不自动继续。|
|本次交接保护记录|[原入口字节备份与资产hash](history/goal_cleared_20261116/preservation_manifest.json)。|

## 数据和资源事实

旧固定TRAIN128母/280视图，DEV40母/88视图，TEST160母/352视图；原TEST已经暴露。后续原TRAIN修补也有多轮暴露，不冒称新留出；更早研究的数据暴露保留原清单，新任务需核对母来源重叠。该清单是历史证据，不锁定新研究的五库组合或配比。

原运行使用Qwen3-8B、thinking OFF，教师Codex CLI `gpt-5.6-sol/high`；完整旧配置在归档CURRENT_GOAL及原run快照中。它们是可复用环境和复现条件，不代替新任务协议；不静默变更后把结果混比。

交接截面累计11741E/329T、reserved0，现金发票/GPU分摊未知。用户的clear不重置账本、未达成贡献或历史费用。本次不新建Goal、不新增研究请求，不设置研究下一步。
