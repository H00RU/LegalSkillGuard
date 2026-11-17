# 统一方案实现进度：2026-11-18

当前Goal保持active，按37a76ff固定方案执行。本次公开快照交付第一版实质实现与可复算的离线结果；真实模型效果、训练矩阵、冻结测试与论文仍在待办中。

M1扩展现有`residual.propose`，从消费者AST派生并组合比较/聚合关系，自动合成配套decoder，保留实体绑定及删去绑定时的合法世界碰撞见证。独立源忠实性检查区分“全部允许补全均支持”“仅部分兼容”“违反来源”，不由原生标签补齐unknown。`InterfaceActor`与生产解码器已有关系接口入口，检查来源、消费者和资产绑定；五库真实provider、实际读者选择及后续母来源技能复用还需接通，不能将fixture通过写成实际学习完成。

M2实现合法源编辑、派生依赖闭包、law_scope/root分别共享的解释、精确允许签名，以及每个补丁跨组累积的解释因素。空K拒绝、全unknown不计成功，实际模型轨迹须核验物理账本。此实现不使用旧风险上界选择器。真实来源的独立K审计和教师补丁更新闭环尚未完成。

数据候选已达到TRAIN128、DEV80、TEST160，维持五库固定配额；CNI已规范为17项原生假设，MAUD仍为固定3任务，公共上下文按唯一原文锚点扩展并记录无法扩展的范围。MAUD的72个TRAIN任务中11个成功取得完整语法section，其余61个保留原生excerpt并显式记录范围未获完整性认证，不能据此声称输入缺口全部解决。旧177份源审不覆盖变更后输入，需要按绑定复核。

Diversity参考适配器的24个固定TRAIN来源，最终标签及两个原生中间标注均一致24/24；这是独立参考能力而非模型准确率。Diversity DEV16/TEST32按固定种子与变体配额准备，同结构TRAIN/已读官方示例组排除；TEST源文与标签均未展示给开发代理、未评分。准备中定位并修复了原生TRAIN/TEST行索引重启导致的ID别名，旧准备版本保留。官方application示例含重复姓名，不修成训练真值；将其所有可能身份绑定保守隔离。

机制/生产传输、源ID和旧付费响应的45项回归检查通过；对应离线回执与源码哈希另存。新Goal物理调用0，累计账本12427、reserved0。教师profile按本机配置固定gpt-6.1-sol/high，执行器Qwen3-8B/thinking OFF；教师模型配置尚未由真实响应确认。

复现离线检查：

```bash
.venv/bin/python -m unittest tests.test_convergence_production_pair tests.test_convergence_relational_synthesis tests.test_convergence_shared_semantics tests.test_convergence_diversity tests.test_convergence_teacher_profile tests.test_revision_reference_chain tests.test_paired_formal_actors tests.test_paired_interface_methods.ResidualMethodTests -v
```

数据准备命令按顺序为`python -m experiments.convergence_prepare_diversity_train`、`python -m experiments.convergence_prepare_diversity_holdout`、`python -m experiments.convergence_normalize_inputs`。原始缓存和连续账本在现有项目内保留，公开快照不附封存TEST、整库账本、权重或凭据。

下一步完成最终曝光/近重复核查和来源绑定、非Airline真实机制链、共同初始化/预算及结构选择的小试20，再执行真实小试与依据失败的优化。当前没有研究driver运行，不从历史队列启动任务。
