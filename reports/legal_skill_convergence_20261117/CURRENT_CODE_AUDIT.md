# 当前完整核心代码审计：354bece

审计日期：2026-11-17。目标提交 `354bece66fd9a0b1e7bc8dab1a6d7159ee141345`；此前证据提交 `1f132108fa326d46118c3c708458fbbafec7bfb2`。只读检查代码、调用入口及现行状态，没有运行研究客户端、修改研究代码、恢复服务器或打开测试。

`code_audit/manifest.json` 保存24个逐文件原始GitHub URL、字节数和SHA256；原文从这些固定提交链接读取。`code_audit/unchanged_core_blobs.json` 保存新旧提交的Git blob对照。

## 结论

**完整同步补齐了此前看不到的实现，现有库已有可复用的关系接口合成骨架和完整训练/评测设施。新方案应在这些模块上接通并扩充真实关系合成，不应另起炉灶。** 同步提交没有推翻 M1/M2 已保存的科学结论，也没有代表正式实验获准恢复。

必须修正此前仅根据 1f132 子集得到的表达：不能说“当前仓库只有部分求值、完全没有关系合成”。354bece 的 `residual.py` 确实实现了比较关系生成、有限语义碰撞检查及成对 decoder 合成；但正式生产覆盖仍主要是 Airline 单变量重量分桶与 OE 公共上下文部分求值，完整关系学习未在五库生产链上得到验证。

## 1. 当前状态与提交含义

[CURRENT_GOAL.md](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/docs/CURRENT_GOAL.md) 首两段明确：这是整个 `legal-skill-current` 核心代码同步，旧段落保留作历史；M1 当前版本停止扩展，M2 继续停止，整 Goal 未完成，正式训练和冻结测试未启动。M1 最后固定验证为复用 18 响应、新增 2 调用/5576 tokens，完整正确 0/4，诊断正分涉及源审 unknown→true。这些结论没有被同步提交改写。

正式入口还有可执行门槛，不只是文档说明：[two_method_formal_study.py 第 164–170 行](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/experiments/two_method_formal_study.py#L164)先检查 `FORMAL_REVISION_HOLD_20261117.json`，再检查 M2 两关，后续还有曝光检查。`M2_EVIDENCE_GATE_20261117.json` 的两关均 false。新方案必须用明确的新协议处理这些状态，不能直接运行旧正式入口。

新旧对照中，以下六个关键实现 Git blob 完全相同：`program_residual.py`、`airline_interfaces.py`、`asset_interfaces.py`、`production_decode.py`、`public_graph_ports.py`、`structural_channel.py`。新增的 29 个 paired_interfaces 文件是全量同步带来的公开可见资产，不能据此推断它们都是本次刚开发或已通过新实验。

## 2. M1 已实现什么

### 通用有限合成核心已存在

[residual.py](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/residual.py)：

- `FiniteModule.build`，第 40–74 行：枚举局部域与上下文，保存完整消费者输出及受保护状态。
- `witness`，第 104–119 行：检查相同编码是否合并了不同的完整语义输出，返回区分世界和上下文。
- `compile_pair`，第 122–149 行：构造序列化的读数 schema、decoder 表及有限域回执。
- `comparison_pairs`，第 162–186 行：从固定程序 AST 的直接字段比较提出 order 关系。
- `value_partition`，第 189–207 行：按完整残余签名生成单个字段的等价类。
- `propose`，第 210–267 行：必要字段细化，优先尝试一个 order 投影，其次单字段分区或字段删除，最后添加锚定布局；最多两个新候选。

这与本轮建议的方法骨架直接吻合，优先复用。当前候选搜索不是多字段关系语法的充分枚举：它一次尝试第一条可通过的比较，只对单坐标分区，不搜索联合比较/聚合/连接的组合。`layout='anchored'` 添加源锚点字段，但合成器没有把多个事件的身份对应本身作为待验证的关系映射。`validate_read` 明确只核对引文包含及 schema，返回 `source_fidelity_verified=False`，不能把它视为事实语义核验。

### Airline 生产实例仍是单重量变量

[two_method_airline_module.py 第 108–155 行](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/experiments/two_method_airline_module.py#L108)使用已保存教师技能 `domestic_main_or_first_bag_total`，设定 101 个整数重量、36 个 cabin/region/geometry 上下文，调用 `FiniteModule` 和 `propose` 生成重量 alphabet。它进一步验证原程序各重量访问只用于已知比较，因此能保存这些比较结果。这是真实的程序派生分桶，不能说完全手填。

但这里没有自动学习跨字段关系：本地输入域只有 `bag_weight_lbs`，`program_source=''`，所以 AST 的 order 候选分支在这个生产实例不会触发。尺寸总和/重量共同超限、主体角色连接、日期相对次序等还没有通过这个入口实例化。

[airline_interfaces.py 第 41–108 行](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/airline_interfaces.py#L41)保留三种固定计划，records 已经按行李记录保留单位引文和属性；local_records 使用前述重量编码。第 168–177 行将编码映射回代表重量进入原消费者。因此“按袋保存属性/加 ID”本身也不能被本轮重新称作新增方法。

本轮 `airline_real_relation.py` 的联合尺寸/重量和分组枚举可以作为已有合成器的补充离线夹具与适配检查，不能替代生产旧技能审核，更不能被计作新模型收益。

### OE 生产实例是公共上下文部分求值

[program_residual.py 第 63–118 行](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/program_residual.py#L63)只替换允许的已知上下文字段，删除闭合布尔分支，不改写未知事实、算术或输出。[two_method_asset_module.py](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/experiments/two_method_asset_module.py)生成不同 governing_regime 的候选并比较 EC/EV 输出。这是可复用的强基线和静态变换工具，不等于非可逆多字段关系学习已经完成。

## 3. 正式训练到底学习什么

[formal_training.py](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/formal_training.py)已经有源审 registry、prefix 数据权限、固定模型/接口哈希、读取缓存、先保存预测再评分以及冻结库交付。`batch` 第 162–165 行要求计划名等于固定 candidate_orders，然后逐个读取；没有在该训练环节调用 `residual.propose` 发明新关系。

[formal_learning.py 第 99–116 行附近](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/formal_learning.py#L99)的 M1 学习实质是：汇总开发/校准 TRAIN 的各计划原生母来源宏平均，以固定候选顺序打破平局，**每个数据集选择一个计划**。输入没有单独的事实忠实性选择约束；因此前述 unknown→true 的偶然正分不能仅靠这里的原生分数选择自动消除。

[formal_actors.py 第 179–205 行](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/formal_actors.py#L179)对 OE 按公开 regime 取计划；其他库取 `unchanged_libraries[dataset]`。现有训练曲线若后来产生，主要体现固定候选选择随前缀数据改变，不能直接叙述成每批不断创造新法律关系技能。

当前设计 128 来源包括：44 development、52 calibration、24 reference_only、8 structure_evaluation。主方法实际有 96 个配对读取来源，不是 128 个独立校准图对。五库为 OpenExempt、SARA_v2_Binary、ContractNLI、RuleArena_Airline、MAUD。这些精确事实来自 [formal_design.py](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/formal_design.py)。

## 4. M2 当前代码不能仍描述为旧 unrestricted 选择器

`formal_learning.select` 现在把 `M2_fixed_interfaces`、`M1_M2` 转到 [formal_observable.select_observable](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/formal_observable.py)。它使用 revised observable 模型，明确记录旧 unidentified unrestricted selector 未执行。`fit_prefix` 仍保存历史 unrestricted/detectable 模型，但不能把保留的拟合分支误认为现部署选择逻辑。

同时，[M2_EVIDENCE_GATE_20261117.json](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/docs/M2_EVIDENCE_GATE_20261117.json)给出新分支的最终结果：六个真实候选族上界仍为 1；有条件的计算例被同假设完整联合轨迹迁移复现，停止扩展。这一科学结论仍有效。新增文件不等于该 M2 已恢复独立贡献。

`formal_design.py` 部分字段仍写 `M2_primary_unknown_mode='unrestricted'`，但实际 formal_study/selector 已有 revised observable 标识。因此后续新协议要统一实际入口和元数据，保留旧协议快照作为历史，不能从单个旧配置字段判断当前主路径。

## 5. 现有消融能证明到哪里

[postfreeze_protocol.py 第 58–74 行](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/postfreeze_protocol.py#L58)明示 refinement_only 与 compression_only 都落到同一个 local_records 端点；[ablation_paths.py](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/legal_skill_guard/paired_interfaces/ablation_paths.py)验证两种路径得到同一分区/同一读取合同。最终准确率不能据此分别归因给“压缩”和“精化”两个操作。

正式矩阵、强对照和封存框架值得复用；具体 M1 消融要围绕新实际算法选择：固定合法接口、仅静态部分求值/单字段桶、相同关系候选池但不使用读者测量，以及完整接口学习。原生程序未变的正确性检查与读取收益必须分别报告。

## 6. 延续实现的最小增量

1. **扩展现有 residual.py，不新建并行合成框架。** 给现有 FiniteModule/compile_pair 增加消费者可验证的联合关系候选、对象/事件分组与身份映射；保留已实现 order、bucket 和静态部分求值作为候选与基线。
2. **把候选接进现有 InterfaceActor/BatchTrainer。** 仍沿用相同冻结执行器、账本、缓存、源审 registry 和保存规则；但候选计划需要版本化生成与适用域，不再只是固定三名称；在 TRAIN 内按真实读取和原生效果选择，同时拒绝来源语义违规的候选证据。
3. **扩充真实消费者覆盖，而不是重复工程预检。** Airline 联合超限适合作为首个可复算接线样例；现有未知字段、完整输入和旧法律消费者覆盖问题继续由原修订处理，不能因为新 H 保持旧 F 就认为 F 已正确。
4. **复用正式编排，更新一次协议。** 预算账本、普通教师技能、SCOPE 适配、独立预测/评分封存、学习曲线和复现模块都已存在。数据暴露与 SARA 库存事实必须保留；新方法候选及其消融与新未暴露评测范围应在新协议中统一，不能绕过旧 hold 直接跑旧队列。

本审计补齐可见代码证据，不重开研究方向，也没有新增任何模型调用。它把“需要开发的方法”收敛成已有核心上的明确增量，避免服务器重复实现现成能力。
