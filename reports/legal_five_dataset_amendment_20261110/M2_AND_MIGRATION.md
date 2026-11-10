# M2 五库混合训练适配与当前 Goal 接续

2026-11-10。代码核验基点：本地 `work/publish-rule-reasoning-v2` 的研究提交 `2a9eeeb`；该工作树无未提交修改。本文件没有改服务器、发模型请求或读取本轮 TEST 标签。GitHub 可见代码不能证明服务器当前 NormBench 工作进度；迁移必须先读服务器现状。

## 1. 固定研究方法，调整训练组成

保留 M2 的**四格、双重中心化、有方向误差交互学习**，不重新换方法。其共享学习对象仍是“两个局部组成决策如何在当前上下文中共同影响结论”，不是五个数据集各训练一套算法。

本轮混合训练配额采用：NormBench 128、SARA Binary 32、ContractNLI 32、ProofWriter OWA depth-5 32、RuleArena Airline 32，共256个来源任务组；各库独立 DEV 16、冻结 TEST 32。正式名单由新的数据 manifest 决定，本文不另选样本。

必须区别统计单位：NormBench 是法条来源，ContractNLI 是母合同，ProofWriter 是完整理论组；SARA 是去重事实/案例组但只覆盖少数税法 section，Airline 是不同原始问题参数组但共享航空政策。五库是五个独立数据集，不等于每库32部不同法规。后两库主要测同政策新案件泛化，不能写成未见法条迁移。

## 2. M2 的公共计算保持不变

对同一来源固定局部节点、原子意义、事实和查询，只改变两个组成决策，形成四个有效候选 `G00,G01,G10,G11`。变量可以是条件父边、分支归属、规则体归属、调用参数连接或作用域连接，但不能同时偷换事实、标签或条件文本。

若存在可用的独立 TRAIN 监督，适配器返回四格预测与 gold 下的损失表 `L00,L01,L10,L11`。共享 M2 head 读取来源/节点表示、四格组合和上下文，预测四格能量 `r`，作双重中心化：

`Qab = rab - row_mean(a) - col_mean(b) + grand_mean`。

训练 `Q` 拟合 `Center(-L)`。四格中只有非可加交互保留下来；单边评分继续学习各自偏好。规范二值分支的特例为 `J=(1-2*y*)*I`、`delta*=-J/4`，沿用原实现及确定性检查。原生三分类或整数任务直接从独立 gold 计算四格损失，不错误套用二值恒等式。

**这不是增加五种 M2。** 共享模块负责四格构造、合法性协议、中心化目标、交互 head、训练及约束解码；每库只提供节点/类型适配、允许的局部变更、可用监督及原生解释/评分。字段没有监督就 mask，而非把缺失填成0。

首版任务损失固定：分类为原生标签0/1错误，Airline为完整整数 exact-match 错误，NormBench为声明域的分支激活 Hamming 错误并单列结构 gold。若四格均错且损失相同，其交互目标自然为零；不能为提高覆盖率把“程序可运行”当正确，也不临时换奖励来制造非零信号。

## 3. 各库可用监督与端到端推断

| 数据集 | TRAIN 可用的独立信息 | M2 可直接监督什么 | 测试真实输入→输出路径 |
|---|---|---|---|
| NormBench | 已审校的分支、条件 AND/OR 树、标签、效果、跨度 | 同节点分支归属/父边四格；原生结构 gold；抽象分支激活误差交互 | 法条原文→M1节点→共享M2条件森林→原生结构输出；按独立金标评分 |
| SARA Binary | TRAIN 原生案例标签；公开参考Prolog及source/structure/角色注释，存监督侧 | 默认原生答案/参考执行监督；仅已核实对齐的字段才开结构mask，不假定Prolog自动等于统一IR gold | 法条及所需公开引用上下文+当前案例事实+问题→规则获取/组合→当前事实读取→执行→Entailment/Contradiction |
| ContractNLI | 母合同、原生假设、三分类标签；非NotMentioned项目的证据跨度 | 证据/任务监督；**没有完整语义图或可执行反事实oracle时mask结构及gold交互loss** | 合同→来源节点/组合→同一任务读出头，结合原生假设→Entailment/Contradiction/NotMentioned及证据 |
| ProofWriter OWA depth-5 | TRAIN formal facts/rules/query与原生三值答案；可核验Horn closure | 规则体/头/参数连接的合法四格；形式结构和原生执行交互 | 原文rules与facts分离→规则获取/组合+事实/查询读取→Horn closure→True/False/Unknown |
| RuleArena Airline | TRAIN问题原始参数；官方 `compute_answer.py` | 当前真实问题的四格整数结果损失；只有源文到代码节点对齐已核实部分才开结构loss | 政策原文→规则获取/组合；当前旅客、行李、航线等公开事实→实例化已学政策→精确总费用 |

### NormBench

这里的 Boolean 见证是**条件满足状态下的结构语义诊断**，不标成真实案件。`depends_on_units` 为空，不补造 defeats/反例外边。共享原子、排除标签转换和域约束沿用已确定的规范化；原生结构指标与其他库原生任务正确率分别报告。

### SARA

参考 Prolog、原始案例机器事实和标签只在 TRAIN 监督或冻结评分侧；规则生成器和测试推断仅看公开自然语言输入。为隔离 M2，可以在 TRAIN 使用参考事实绑定，明确标为组件监督；端到端不能偷偷使用这些事实。

旧适配器只提供题目对应的一个 section，真实任务可能引用其他 section。先按公开引用补足可得上下文并记录仍未解决的引用；若固定任务协议只提供有限上下文，双方使用同一输入，不能由 gold 程序替生成器补规则。32个 TRAIN 案例的结构监督可共享同一法条，但不把重复结构计作32种新规则。

当前 `oracles.py` 没有 SARA reference wrapper。需接入隔离的参考 Prolog 执行和固定依赖；先验证官方 TRAIN 原例再开放监督。没有通过的 oracle 路径先只用官方原生标签，不用未经核实的自行转译作为裁判。

首版不以给全部 SARA 条文新增统一IR gold为先决条件。默认 `structure_gold_mask=0`，已存在且经过检查的个别source/structure对应可逐字段开启；官方原生答案不需要等待统一IR对齐。若候选程序在原始案例上已有可靠执行接口，四格原生答案损失可用；若仍由通用模型直接读出而没有可靠候选执行，则按ContractNLI同样mask其“语义交互金标”路径，不能让模型自判补齐。

### ContractNLI：弱监督也参加混合学习，但不伪造 M2 gold

合同不存在一般“案件事实”区；文档是规则/声明来源，hypothesis是查询。证据跨度支持定位，不等于完整作用域、例外或事件变量真值。NotMentioned不是Contradiction，也不是“当前程序没有规则”的同义词。

固定原生假设范围，首版推荐所有17种官方假设均可读出，按母合同归组；若已有运行只选一个/少数假设，则在新manifest明确，不混称完整任务。训练一份合同的多个假设仍只算一个来源组，loss按母合同归一化。

共享 M1/M2 仍对合同生成/组合来源节点；原生 NLI 读出可由同一 Qwen 任务头消费预测图、合同和假设。以原生标签训练可识别的任务部分、证据定位和 M1 的合法弱监督；**没有独立执行语义时 `structure_gold_mask=0`、`m2_directed_interaction_mask=0`**。不能让任务头替四个候选自判“正确图”，再把其判断当金标交互。ContractNLI 在混合训练中必须有真实非零的原生任务/证据更新，不因 M2 mask 而从训练计数消失。

原生预测头读取完整合同可能不依赖图；必须记录图使用/替换消融和M2有效覆盖，允许结论为“该库暂未观察到M2增益”，不能把任务头直接答对计作符号组合成功。最终五库指标仍完整包含该库，无需新增大规模全图标注才能开始。

### ProofWriter

使用官方 OWA，而非缺失即False。显式负事实与未知是不同状态。模型输入不含 formal representation/proof；它们只在 TRAIN 监督和独立评分侧。候选四格要保持全部局部原子和规则节点，通过变量安全、类型和引用检查；不通过的四格不强凑。

已有 `public_horn.py` 是固定受限英语解析器，可作强基线或无模型格式检查，不能将其直接成功宣称为 M1 学会获取。已有 `horn.py` 可以作为所有方法共享的执行器；重命名 Horn closure 不算方法贡献。

### Airline

官方整数oracle可在 TRAIN 当前原始参数上评分；受支持扰动必须满足官方函数输入域并另记oracle访问。评分代码不能作为测试预测工具。政策文本与实例事实分开缓存，当前机票价格、行李数量/尺寸/重量不能从旧案例继承。

参考代码能提供答案不自动意味着源文—AST全部已对齐；首版无对齐的结构边mask，保留原生结果监督。共享M2从合法条件/数值作用域四格获得原生整数损失；具体数值节点语义由已有解释器执行，不再写一套航空特例“方法”。

## 4. 混合训练与监督掩码

按256来源组建立固定打乱/交错的epoch顺序；同一模型的共享 M1、M2 参数跨五库更新，不把五次各自训练拼成“混合训练”。每库最少完成一次真实训练前向/反向与原生 DEV 推断，记录实际更新数。

每个训练来源携带：

```text
dataset_id, source_group, public_source, facts, query_or_queries
supervision_type: dense_structure | reference_execution | native_label_evidence
structure_gold_mask, reference_oracle_mask, m2_directed_interaction_mask
legal_input_domain, original_split, source_hash, grading_hash
```

损失按来源而非题目/候选/见证数量归一化。128条NormBench和四库各32条是数据配额；训练可使用预先固定的数据集权重，权重在小试后锁定，并给所有强对照相同权重。需报告每库：参与更新的来源数、有效四格数、非零交互比例、结构/任务监督比例及未覆盖原因。

没有四格的来源照常贡献可用任务/结构监督；不能为了让每个来源都有交互而造一个错误的第四候选。测试端也可以使用候选间差异发现/分组，但没有测试gold，不能据此判断哪一图正确。

实验臂名称、数量及执行顺序以根方案的统一协议为准，本文件不另锁臂数。M2 所需归因包括普通组合器、等容量高阶组合器及 SQLoom 风格同四格/同高阶head/同监督适配。各库使用同一个架构及相同mask。只有M2缺失gold却给对照更多标签、或反向不给对照参考程序，都不公平。

## 5. 已有代码的实际复用与必要修正

以下均在 `2a9eeeb` 核验，不假定服务器尚未完成更新。

| 现有路径 | 复用内容 | 必需修正/限制 |
|---|---|---|
| `legal_skill_guard/rr/adapters.py` | `Prepared`、public/grade分离、SARA/ContractNLI/ProofWriter/Airline解析、来源聚类 | 新增NormBench入口；SARA引用上下文；ContractNLI恢复证据及选定假设集合；保留各原生group |
| `legal_skill_guard/rr/partitions.py` | 规范化、跨split连通组去重、内容hash | 旧配额硬编码OE32+四库24、DEV8、TEST32，改为显式新protocol配额；不要原地覆盖旧manifest |
| `legal_skill_guard/rr/scoring.py` | 原生三分类/二分类标签、Airline整数exact-match、失败纳入分母 | 新NormBench结构评分；动态数据集集合；不要把NormBench树F1硬改成案件accuracy，也别强行保留旧OE假定 |
| `legal_skill_guard/rr/source_structure.py` | rule/fact/query边界、原文offset、引用信息 | 加NormBench来源边界；新增中文跨度处理做局部改动；不要沿用只认英语标题的假设 |
| `legal_skill_guard/rr/horn.py`、`oracles.py` | Horn执行、ProofWriter reference解析、Airline reference wrapper | 原生reference始终监督/评分专用；增加核实后的SARA wrapper，不把wrapper接到预测入口 |
| `legal_skill_guard/rr/source_program.py`、`scoped_program.py`、`source_execution.py` | 已有可执行表达式、类型/作用域检查、原生输出格式 | 复用具体检查器和解释器；不要重新引入旧A证书作为新Goal验收门槛；NormBench输出单独适配 |
| `legal_skill_guard/rr/airline_application.py` | 相同政策库复用、当前事实重新绑定 | 其模板匹配是工程组件/基线，不当新M2；核实所有当前行李均进入总费用 |
| `legal_skill_guard/rr/method_client.py`、`client.py` | thinking配置、请求hash、实际token与耗时采集 | 沿用当前获授权的模型配置，不为接五库重跑thinking搜索 |
| `legal_skill_guard/rr/method_ledger.py` | 沿用旧账本的原子预约、缓存、真实请求累计；不恢复旧轮次/额度 | 新run binding/allowlist；它当前只允许TRAIN/DEV，冻结TEST阶段须按该阶段授权扩展，不能悄悄开TEST |
| `legal_skill_guard/rr/checkpoint.py`及当前服务器新M1/M2模块 | 保存/恢复、模型和optimizer状态（以服务器实际实现为准） | 用新manifest/hash绑定新阶段，旧checkpoint保留，别改运行中绑定文件 |

**两个不宜直接套用的旧入口：**

1. `data_store.py:PreflightData` 写死20来源、每库4条及旧packet路径；`formal.py` 写死128来源、8批、B8冻结和旧teacher约束。复用hash/隔离逻辑即可，不为迁就旧入口把256来源伪装成128，也不恢复历史6000/20或预检修复轮次。
2. `contract_scope_learning.py` 的 `QUERIES` 只有4个假设；`execute()` 返回 `preserved_conditions`，但没有执行这些条件。`contract_compiler_runtime.py` 又会按query切片并标注 `whole_graph_accepted=False`。它们可借鉴安全执行、引用与证据校验，不能直接声称覆盖17种假设或已实现完整合同语义。

优先扩展服务器当前已实现的 M1/M2 训练器及适配层。若尚无公共接口，只加一个薄的 `semantic_adapter` 协议（节点、有效四格、可用监督、原生执行/读出）及一个新protocol manifest；不要复制五套训练器，也不要为未来数据重建全仓框架。

## 6. 当前服务器怎样继续

1. **读取现实状态。** 服务器先读当前goal/交接、分支、工作区、真实PID、账本和已落盘checkpoint；本文件中的 `2a9eeeb` 只是审计基点，不要求回退到该提交。已有同等实现和验证直接复用。
2. **当前Goal接续。** 将“NormBench单库主训练”更新为“五库共享方法256来源”的当前交付范围；不重开选题、不重置Goal或账本。已完成的 NormBench 适配、M1/M2模块、四格计算、中心化测试和结构预检仍有效。
3. **安全切换批次边界。** 若有正在执行的请求/批次，先确认真实身份并保存其结果或checkpoint，再调整后续调度。不要同一输入重复派发；不要在运行中改绑定的配置、数据或模型文件。旧单库正式结果保留，单列为原阶段。
4. **建立新manifest和训练状态。** 按最终五库数据清单生成新路径、新hash及新run ID；同一Goal允许不同run ID，这不是新Goal。旧结果只在输入、模型、代码和监督语义完全一致时复用。
5. **处理已暴露的单库样本。** 若旧NormBench模型已经训练超过本轮128条，不得把这些额外暴露藏起来再写“仅256混合训练”。正式可比试验从共同原始模型开始，在新256名单内完成共同初始化及后续混合学习；复用解析缓存和标注，旧单库checkpoint保留作pilot，不启动额外预训练比较支线。旧已看标签来源不得转入新DEV/TEST。尚未真实训练则无需无谓重跑。
6. **完成五库最小学习闭环。** 每库选新TRAIN清单内的固定少量来源，跑共享参数更新、原生输出、保存/恢复和DEV推断；这一步补上新库缺失能力，已有NormBench同等证据不重复。ContractNLI缺图gold按mask处理，不为此停住整阶段或新建大标注工程。
7. **继续已授权的完整训练与DEV。** 当前Goal原已授权256训练及DEV，本补充将其替换为五库混合256训练和各库16来源DEV。五库预检通过后自主继续完整混合训练、保存冻结checkpoint并完成五库DEV；不能只交实现或小试便标记完成。冻结TEST32/库仍封存，待本阶段报告复核后进入下一阶段；不新增付费服务授权。

## 7. 本次应交付什么

- 新五库manifest，256 TRAIN、每库16 DEV和32 TEST的来源计数、去重/历史暴露记录；TEST金标独立封存。
- 一个共享M1/M2训练入口、各库薄适配器、可用监督mask和原生输出链路。
- 五库真实训练更新与DEV记录，来源级主路径/fallback/无效输出区分；M2有效四格及非零目标覆盖。
- 原生指标分库报告，宏平均只在清楚定义的归一化任务分数上计算；NormBench结构指标同时保留。跨数据学习通过共享更新曲线及固定DEV分库结果观察，不能拿混合总分掩盖单库退化。
- 完整256来源混合训练、五库各16来源DEV结果、模型/训练状态与配置冻结、完整账本和实际新增成本，以及下一阶段TEST可运行命令。工程测试、无梯度演示、小试或仅诊断报告不代替当前Goal完成；本阶段不打开冻结TEST。

五库扩展不要求每种机制在每库都有同样密集的gold，也不要求五库全涨。它要求五库都参加真实混合学习并保留原生语义，M2的监督来源、作用和边界可追溯，最终效果由冻结协议下的实测决定。
