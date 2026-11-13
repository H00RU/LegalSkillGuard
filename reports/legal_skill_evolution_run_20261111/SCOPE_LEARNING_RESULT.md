# 源作用域学习的最小真实原型

2026-11-13。同一 Goal active、未完成。本次完成了真实 TRAIN 监督获取、显式学习算法、可运行更新器和组件对照；没有新增来源、执行模型调用、DEV/TEST或完整训练。

**原四份 TRAIN 中确有一条限定同时作用于多个处置条款，但当前结构归纳没有取得独立优势。** 新监督与更新器保留为公共研究资产，不占第一贡献；第二项也未成立。不会为这个未获支持的几何归纳器继续派发模型。

## 学了什么，实际执行了什么

[真实教师获取](scope_learning_evidence/raw/execution/teacher.json)从原四母合同取得10个条款单元、13条关系记录，展开为15个作用边。关系区分限定、替代、触发继承、信息指代和后续履行；一条关系可指向多个条款。没有读取新的复用材料或native标签来获得这些关系。教师判断有出处校验，但不是独立人工gold或形式化法律真值。[输入](scope_learning_evidence/raw/execution/input.json)、[冻结协议](scope_learning_evidence/raw/execution/protocol.json)。

学习对象是条件化的、多目标的条款作用关系。更新算法复用已实现的精确 DNF/set-cover：从完整审查产生正负边，不完整审查不把遗漏边当负例；使用类型、相对位置、显式段落引用和文字线索，不用合同名、绝对ID或native标签。实际拟合5类策略。DNF是采用的成熟组件，不把算法名字、边数或训练重放当创新。[实现](../../legal_skill_guard/skill_evolution/source_influence_learning.py)、[获取入口](../../experiments/legal_skill_evolution_scope_learning.py)、[学习入口](../../experiments/legal_skill_evolution_scope_induction.py)。

真实442c36的第51单位“本段第6条”中依法保留记录副本的许可，同时限定48、49、50中的处置安排。取得的全量拟合策略和普通显式同段匹配均返回这三个目标。更新器已用**既有真实IR**执行：给第48单位原返还义务添加第51单位的保留例外，并保留原书面指示例外；原59构造子类型检查通过。**两者修订后的IR逐项相同，4个native答案也未改变。** 原IR没有49/50对应完整根，更新器没有补造；这不构成完整源语义验收。[修订前后与原消费者重放](scope_learning_evidence/raw/execution/actual_scope_update.json)。

这与旧scope模板未被G消费的情况不同：本次作用边确实改变了真实规范。然而，实际改动被简单段落控制吸收，仍不能作为额外方法贡献。

## 实际组件比较

按母合同留一，仅在其余三母合同上拟合；各臂共享取得的局部种类、监督和特征。评估共120个关系候选对，其中15个正边，来自4个母合同，不能算120个独立来源。训练全量拟合通过不表示跨来源通过。

|组件|TP|FP|FN|关系微F1|
|---|---:|---:|---:|---:|
|学习的结构策略|8|33|7|.2857|
|最近适用条款|10|17|5|.4762|
|显式同段匹配，否则最近条款|12|23|3|.4800|

[完整策略、每母合同/关系及所有预测](scope_learning_evidence/raw/execution/induction/result.json)。这是使用教师取得局部种类的离线组件检查，**不是8B真实预测新关系、端到端获取或新盲测**。最近/段落基线的关系存在性判断也较粗，因此只是简单结构比较；没有据此宣布已完成全部强对照。学习器连这个比较都未显示收益，且真实IR效果完全相同，足以决定不扩真实队列。没有按留一结果增加特征、扫描超参或追加来源。

当前几何归纳器需要在已有关系形态之间推广，不能依靠稀疏结构特征取得新法律语义。复杂作用边大多集中于一个母合同；缺少某类关系正例的留一折保持未解决，不默认产生万能规则。这是该实例与学习器的具体结果，不证明法律作用域学习整体不可行。

## 校正下一步的真实反馈

从原获取 TRAIN 的既有请求中整理了17个与已得示例可对齐的字段观察，11个物理请求、**一个母合同**。其中4次与示例标签不同，但不能全当法律错误：

- 动作字段sr_3_action未被实际保留禁止分支读取；改变为示例标签，原程序完整输出不变。
- designated_recipient_holder与named_service_actor可能指同一Volunteer；一个正例不证明另一个描述错误，等价性保持未知。
- 两次“没有保留对象范围”的选择与第30单位明确禁止保留副本、笔记、摘要矛盾，该字段实际被读取；正确类别已经在允许选项中。

[原物理观察](scope_learning_evidence/raw/execution/training_semantic_feedback.json)、[实际lookup、字段干预和源语义复核](scope_learning_evidence/raw/execution/training_feedback_semantic_review.json)。这些观察不含两份已结算复用来源，不据其标签修补。**下一步不能把单标签不一致自动当错误，也不能把已有正确选项下的错读全部归为需要扩schema。**

## 近邻与当前决定

[GEPA](https://arxiv.org/html/2507.19457v1)已有模块反思、实际轨迹反馈、候选验证与Pareto选择；本次还核对了作者[反思提议代码](https://github.com/gepa-ai/gepa/blob/main/src/gepa/proposer/reflective_mutation/reflective_mutation.py)与[接纳路径](https://github.com/gepa-ai/gepa/blob/main/src/gepa/core/engine.py)。[Socratic Skill Learning](https://arxiv.org/html/2610.17860v1)已有教师在实践中指导、持续问题记录与冻结后的迁移验证。因此“教师修订”“反思历史”“多模块”都不足以构成我们的差异。本次只阅读，没有执行其软件或复现其结果。[阅读范围与字节哈希](scope_learning_evidence/raw/execution/focused_literature_receipt.json)。

集中决定：**停止把词面/位置 DNF 或普通同段回填作为核心贡献候选。** 保留新监督、真实例外更新器和简单控制。下一实际工作转向获取程序的语义反馈闭环：只把有源矛盾且被实际消费的解释作为可靠负反馈，对合法别名、未定等价与未消费字段保留旧行为；与同信息的普通反思修订对齐后，再决定有限真实比较。该闭环及其超出强控制的增量尚未成立，不能预先占据第一贡献。两项独立贡献与原Goal验收条件保持。

## 费用与保全

本次新增**0E/1T**，累计**9370E/190T、9560行、在途0**；原9559行逐条不变。教师150.035秒，输入39662、输出7375 token（含5810 reasoning，不重复加计）；教师发票和GPU分摊未知，不能记零。新增执行API现金0，无执行生成。首次命名空间预检在预留前被拒，0物理请求；原失败协议/源码和纠正后的绑定均保存。[完整费用及请求](scope_learning_evidence/cost_and_preservation.json)。

239项相关回归通过；真实retention_permission的4个实参和retention_exception的3个实参按原类型定义转换，旧学习函数保持，旧源码快照保存。原五库、划分、已冻结结果、thinking OFF及模型配置保持。未启动新完整训练或正式评测，不修改main。
