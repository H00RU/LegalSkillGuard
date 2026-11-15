# 真实TRAIN误读修复、教师更新及复用验证（2026-11-15）

**这轮取得了真实学习与执行进展，但没有证明两项独立贡献。** 方法臂在原TRAIN的§151案件从未解决变为执行原法律程序并答对；同信息普通教师也修好了相同的亲属误读，且同一学得契约关闭来源约束编译后没有变差。因此不能把这次修复包装成第二项创新成立。原40母DEV仍为ours46.884%、NoC48.134%，没有重跑或改写。

## 已执行的具体改动与结果

1. **把已有源前提检查同步到生成约束。** 原案件只说一般§151，两个已付费输出却分别生成§151(b)/(c)精确前提，随后转换失败。新schema按当前facts中的精确引用约束这些原生前提，问题、完整法条和原生答案不提供事实许可。两臂各一次真实读取，均不再生成这些无依据前提；unknown/null仍保持未读。整案当时仍未解决，因此没有把两次格式/约束通过算成方法成功。
2. **真正调用教师修订观察schema和转换程序。** 原模型把“结婚”读成兄弟或父子关系，并捏造共同居所。现有源审查的“禁止捏造亲属关系”漏了brother/sister/sibling，已对两臂一致补齐。两次真实教师请求，各给出两个完整成对版本，学得关系类别—来源词—方向之间的约束；修订具有实际代码、schema、父版本和错误ID。两例用于当前修补，另一个原TRAIN来源在派发前固定、未放入本次教师任务；三例均有旧B8暴露，不称新盲测。
3. **真实读取与选择。** 四个新版本中，方法两版均在两例上通过既定局部源检查并完成转换；普通教师第一版也通过，第二版漏读/反转了实际son关系。按相同源失败与未解决标准，两臂均选择版本0。旧库在无亲属案件上仍产生错误亲属事实并转换失败。

|增量整案执行（仅原TRAIN两例）|方法臂|普通教师臂|
|---|---:|---:|
|修复前主路径原生正确|1/2|0/2|
|修复后主路径原生正确|2/2|0/2|

这不是两次新整案读取：仅family组件新生成，其余真实已付费观察保持不变，经当前转换及原生法律程序执行。普通教师在family组件也已修好，整案仍被其他未改变的付款/申报组件阻断。这个差额包含继承库的差异，不是新机制的独立归因，也不是DEV提升。一般§151案件通过了对应的两项现有局部源检查；这些检查不证明全部源语义。

## 固定复用、离线恢复与真实消融

固定复用案明确说Alice和Bob在给定期间住同一个家，并有明确son关系。两臂新观察都读出了son；初次转换均未完成：方法臂重复描述同一居住事实，其中一种语法形式被拒绝，普通教师的形式检查也把“同一住处”误当成必须再提供独立地址。

已完成**0调用、保持事实的确定性恢复**：仅枚举原学得schema允许的有限语法标记，保留原人物、地点、日期、原文和witnesses；用原学得转换器原样验证，要求全部合法解释得到同一事实集。重复描述只在世界属性与原始证据完全相同的情况下合并。两臂均恢复完整转换，son、两人的同住关系和原文日期保持，未补地址、国家或缺失字段。原始响应保持不变，恢复回执公开；这是双方共享的执行修复，不计作教师新学技能或独立收益。该例没有补齐整案其他读取，因此不计作整案原生成功。

同一方法版本在同一无亲属案件上做了一次**关闭来源令牌编译**的真实消融：schema的结构规范化、prompt、转换器及法律程序相同，只取消来源词候选收缩。结果仍完成转换、局部源检查也通过。**本次消融增量为0；普通教师吸收了亲属修复。** 不继续给这组三例反复补调用追求差额，来源约束编译保留为公共执行能力。

## 已修复的接口缺陷及证据边界

新schema的组合写法暴露了解码器对公共必填字段的支持缺陷。首个真实生成只返回关系类别/来源标记，严格host正确拒绝，费用保留。已把公共对象约束与局部分支做等价分配：`B∧oneOf(Ci) = oneOf(B∧Ci)`，同时处理实际的`allOf:[{oneOf:...}]`写法。原始精确wire字节重建的grammar会接受该缺字段响应，修复后拒绝，host始终拒绝；没有补齐缺失人物或事实。18个候选/来源schema均通过离线grammar编译，随后才真实重试；教师不重发。当前39项针对性回归通过，包括真实失败、字段完整性、源约束、unknown、源属性不变及执行/残余转换等价。

另外修复了原TRAIN纯年度范围§68(f)被遗漏的公开between/3计算，0模型、单列公共算术；以及C共享消费者把“完整销毁”与“完整返还”不对称处理的问题。C的正常24母源输出在两臂下重执行，修复前后仍为93/96与92/96。它们是实际缺陷修复，不是核心学习增益，未改写原冻结库和原结果。

## 研究判断与下一项工作

当前新增机制仍需相对近邻和强控制成立。约束解码已有[PICARD](https://aclanthology.org/2021.emnlp-main.779/)，上下文相关语义约束已有[Synchromesh](https://www.microsoft.com/en-us/research/publication/synchromesh-reliable-code-generation-from-pre-trained-language-models/)，按输入产生专门grammar已有[Grammar Prompting](https://proceedings.neurips.cc/paper_files/paper/2023/hash/cd40d0d65bfebb894ccc9ea822b47fa8-Abstract-Conference.html)。因此本轮代码可证明“已有正确契约怎样进入真实读取与转换”，不能仅凭使用grammar或一次案件恢复认定新贡献；从错误学习了哪些可复用语义条件及其独立价值仍是目标。

C的原DEV负作用没有被上述消费者小修解决。下一项回到C的实际表示/组合选解与原生题目消费衔接，复用已有不可表达反证，不延长同一失败搜索、不为了拟合标签补造角色/触发/OR语义。第二项保留已学版本和本次否定证据，不在这组三例上继续生成；有明确的新语义/学习算法改动及离线证据后再验证。Goal继续active、未完成，不开TEST或论文。

## 原始记录、实现与累计账本

本轮新增**executor14、teacher2**，包括一次HTTP完成但严格输出验证失败的请求；全部结算，未发生自动重试或教师重发。累计executor10853、teacher303，reserved=0。本轮executor输入25610、输出5006 tokens；teacher输入51114、输出33530 tokens，其中reasoning_output14948是原usage子字段，不重复相加。现金发票与GPU分摊未知。前11140条既有账本行逐项hash不变。

- [逐次请求、usage与旧行保存证明](../raw/legal_skill_evolution_source_guard_stage_review_20261115/cost.json)
- [两臂真实教师输入](../raw/legal_skill_evolution_family_source_guard_20261115/teacher_task.json)；[方法教师完整输出](../raw/legal_skill_evolution_family_source_guard_20261115/CoverageRecombine/teacher.json)；[普通教师完整输出](../raw/legal_skill_evolution_family_source_guard_20261115/FreeGlobalUpdate/teacher.json)
- [选择、源失败与未解决统计](../raw/legal_skill_evolution_family_guard_validation_union_fix_20261115/selected.json)；[增量整案执行及原生评分](../raw/legal_skill_evolution_family_guard_validation_union_fix_20261115/incremental_whole_cases.json.gz)；[同契约真实消融](../raw/legal_skill_evolution_family_guard_validation_union_fix_20261115/same_component_uncompiled.json)
- [原始typed失败与精确wire回归](../raw/legal_skill_evolution_family_guard_validation_union_fix_20261115/actual_decoder_failure_regression.json)；[18个schema离线检查](../raw/legal_skill_evolution_family_guard_validation_union_fix_20261115/offline_grammar_ready.json)
- [方法复用原始响应及转换失败](../raw/legal_skill_evolution_family_guard_validation_union_fix_20261115/family_results/CoverageRecombine/0/ac4c0afe669059f383204d9bc67c4554f703e63cf5059745e63405b2e1d545cf.json)
- [双方0调用语义保持恢复](../raw/legal_skill_evolution_residence_scope_recovery_20261115/result.json)；[C共享消费者修复与实际重执行](../raw/legal_skill_evolution_native_consumer_symmetry_20261115/result.json)

大文件按主索引提供.gz原始完整副本。实现只在研究开发分支，main不改。
