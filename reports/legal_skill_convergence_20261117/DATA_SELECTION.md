# 五来源选择、核验与划分

2026-11-18。正式选择：OpenExempt、ContractNLI、MAUD、RuleArena Airline、LegalBench Diversity Jurisdiction。保留四个现有适配库，只用Diversity替换原计划尚未接入的Housing。选择基于任务结构和工程可核验性，未使用新方法的模型分数挑库。

## 1. 为什么选这五个

| 来源 | 数据性质与主要价值 | 已有依据 | 本次角色 |
|---|---|---|---|
| OpenExempt | 法律财产豁免；资产、身份及额度耦合 | 已有原生EC/EV评分、源审核和历史错误；默认条件遗漏须共同修复 | 主体/资产绑定及非线性额度 |
| ContractNLI | 真实保密合同，原生17假设及证据span | 官方数据607合同；项目24训练来源有不同义务标签结构；未证明新M1收益 | 长文本定义、主体和例外作用域 |
| MAUD | 真实并购合同、条款分类 | 官方152合同；项目24训练来源中11个存在两类义务的疫情例外标签差异；未证明错读率 | 同文档中不同义务的限定条件 |
| Airline | 政策数量推理，原生可执行评分 | 已有联合关系确定性原型；仍未测得新模型增益 | 数值/对象耦合的清晰检验 |
| Diversity Jurisdiction | 法律规则应用的程序生成案件，不是自然裁判文书 | 六种原被告/诉求结构，官方提供最终及两个中间标注；本次24例离线适配一致 | 非Airline实体绑定、聚合范围与关系监督 |

这提供数值、主体关系、合同作用域三种结构；不是要求五库每题都受益。真实合同负责检验自然文本适用性，Diversity提供结构可控的法律任务。不要把Diversity的六个变体、ContractNLI的17假设、MAUD的多个分类任务算成多个独立来源。

原始出处：[ContractNLI任务定义](https://stanfordnlp.github.io/contract-nli/)、[MAUD论文](https://aclanthology.org/2023.emnlp-main.1019/)、[RuleArena官方代码](https://github.com/SkyRiver-2000/RuleArena)、[Diversity任务定义](https://github.com/HazyResearch/legalbench/blob/main/tasks/diversity_6/README.md)。项目数据结构统计见[已有训练审计](../two_method_followthrough_20261116/data_audit/REPORT.md)，代码/历史结果边界见[当前核心审计](CURRENT_CODE_AUDIT.md)。

## 2. Housing与SARA为何不进入本轮

[Housing原始数据卡](https://huggingface.co/datasets/reglab/housing_qa/blob/main/README.md)描述的是“问题×辖区”的住房法规是非问答，正文例子为某地是否有相关法律；不能默认每题都有租客案件、通知日期及可交换的事实事件。它有法律价值，但上一版把它直接对应到案件时间绑定过于宽泛。为减少新消费者定义和事实接口工程，本轮用已核实有显式主体/诉求结构的Diversity替代，Housing不进入等待选择队列。

SARA已有训练与诊断资产继续用于回归，已暴露库存不再充当新盲测。DeonticBench中的SARA/Airline是来源复用，不能作为新增独立数据集。暂不加入USCIS或其他新库，避免把两方法实现变成另一轮开放式选题。

## 3. Diversity的实际核验

数据版本固定为Hugging Face `nguha/legalbench@daec8237410aa23e3faf4bc41ad8b3a7e1696826`。六变体各6个原生TRAIN；服务元数据显示各300个原生TEST行。行数不是去重后独立母来源数，最终库存仍核对服务器既往暴露。

本次按索引固定每变体0—3，共24个TRAIN行，未根据结果筛选。确定性适配器提取原被告、州籍与诉求，按该基准约定核对：跨原被告州籍区别；同一原被告对内合计、不同对不合计；所有受评对的金额条件；最终Yes/No。24/24同时符合`parties_are_diverse`、`aic_is_met`与`answer`；选择行无完全相同文本。脚本只说明该原生任务能接入独立评分，不是新M1算法或弱模型效果。

复现：在本目录运行 `python audit_diversity.py`，结果写入[data_audit/DIVERSITY_TRAIN_AUDIT.json](data_audit/DIVERSITY_TRAIN_AUDIT.json)。原始文件URL、hash、行ID和核验结果均保留；脚本不请求原生TEST正文/标签。不要将此基准约定扩写成一般法律意见，也不要把规则解析脚本独占接到主方法预测路径。

**标注边界。** 三个原生标注字段是评分/监督，不是执行模型的输入。M1可以提出局部跨角色同州比较、同对诉求绑定等关系，不能直接读一个“本案有管辖权”字段来绕过问题。所有臂获得相同公共规则文本；few-shot只能来自锁定TRAIN。此次读过的官方Diversity-6提示范例（含额外两个原生TRAIN例及application范例）记设计暴露，正文及近重复不得进入本项目TEST。不要直接复制带额外已解范例的官方提示。

## 4. 一次锁定划分

- TRAIN：OE32，其他四库各24，共128；Diversity优先上述预选24。按母来源/合同/语义近重复去重；如预选存在确定重复，用预定原生TRAIN索引顺序补齐，记录原因。不得按成绩替换。
- DEV：各16，可以使用已暴露但不属于TRAIN及其近重复组的历史开发来源。Diversity可从原生TEST池按固定种子作本项目开发划分；其余未暴露候选先封存。
- TEST：各32新来源，必须排除所有历史暴露、开发、训练及其近重复组；MAUD的39个候选优先留给TEST，不再占16个新DEV。此处是配额，最终manifest尚未生成，不能写“划分已完成”。
- 将`original_dataset / revision / native_split / native_id / mother_group / project_split / exposure_status / content_hash`写入清单，同时锁定假设/问题/类别/视图集合、评分与聚合方式，并注明完整原生任务或固定子任务。划分器与评分器读取封存数据，开发代理只看允许的元数据和训练/开发结果；禁止全目录搜索原生测试文本/标签。
- Diversity在姓名替换下同州籍相等模式、同诉求归属、同金额向量的实例归同近重复组，跨变体一并检查；不要把整个variant当成一个母来源，也不能只按文本hash去重。合同沿用文档/修订/模板近重复组。
- 正式清单前固定种子45和标签无关的组排序规则；Diversity的DEV配额按六变体`[2,2,3,3,3,3]`、TEST按`[5,5,5,5,6,6]`分层抽取。报告各变体覆盖，整族只计一个数据源。

只有明确的重复/数据损坏/已暴露能改变成员；原生答案难、方法未触发、模型0分都不是剔除标准。若服务器核实某库合格库存确实不足，先穷尽已选来源的合法库存并报告精确差额；不悄悄改成另一个库、不复用已暴露测试充数。这是数据真实性边界，不是效果停工门槛。

## 5. 指标与论证范围

按各库原生评分保留全量结果；Diversity使用[官方balanced accuracy评估](https://github.com/HazyResearch/legalbench/blob/main/evaluation.py)，另附普通accuracy及两个中间字段的诊断准确率。中间字段准确不是独立新任务成绩。所有置信区间按母来源/近重复组聚类；本项目小规模自定义切分不能冒充官方全测试排名。

OE/Airline的公共规则包、Diversity的固定管辖规则，与合同文档的变化不是同一种泛化。论文分别报告新案件、跨文档与跨库技能复用，不把五库分数自动解释为新法规泛化。两项贡献需要实际学习/更新和原生指标证据，不以数据结构存在代替效果。
