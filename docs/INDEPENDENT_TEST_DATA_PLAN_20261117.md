# 独立测试数据安排（提案，未派发）

当前五库训练资产、128 个母来源角色及 177 个源文参考视图全部保留。
原 DEV72/TEST136 已暴露，只能保留为开发、回归和诊断证据。
本提案未改变冻结集合，也未下载、阅读或评分补充数据的 TEST 实例。

新增TRAIN证据：一个MAUD原生片段遗漏了其同一普通经营条款后续的COVID例外，
已交付按唯一原文锚点恢复完整Section的工具和版本化输入提案，见
[上下文修订](../reports/two_method_followthrough_20261116/MAUD_CONTEXT_REPAIR_20261117.md)。
因此MAUD的剩余候选数不保证片段对标签的输入充分性。若采用恢复上下文，必须先在TRAIN固定规则，
另冻共同输入并对七系统一致供给；原生片段成绩与恢复上下文诊断分列。
不能为解决标签缺口而挑读TEST，也不能把更长上下文或旧母来源改写算成新的盲测样本。

## 已核实的官方库存

元数据审计命令：`.venv/bin/python -m experiments.two_method_remaining_stock_audit`。
完整固定 SARA 另有 `two_method_sara_remaining_inventory` 审计。
native 适配器机械分离原始标注；不打开 prepared DEV/TEST grading，
不输出或保存新的原生标签、问题、源文。库存模式已显式禁止评分和 Airline oracle 执行。

| 来源 | 当前未使用候选母来源 | 原生 split | 本轮操作 |
|---|---:|---|---|
| SARA Binary | 0 | 固定 release 共 96 个合并母来源，80 个旧暴露、16 个新暴露 | 保留 TRAIN 与历史诊断 |
| CNI | 421 | train335 / dev29 / test57 | 仅候选键、隔离组和计数 |
| MAUD | 39 | 原生问题按完整契约合组 | 同上 |
| Airline | 172 | 官方 unsplit | 同上 |
| OE | 80 | 原固定官方生成池的剩余部分 | 同上，不再生成或重抽 |

这些是按当前暴露索引、调用和已知事件排除后的候选上限；不是最终盲测承诺，
也不意味着当前固定 F 能处理。冻结前还需检查完整父来源与模板隔离。
不能按参考输入得分删去域外题，再把余下子集说成原库整体能力。

官方 [SARA v2](https://nlp.jhu.edu/law/sara_v2/) 的更新重点是结构／参数标注。
[v3/3.1](https://nlp.jhu.edu/law/sara_v3/) 是原案例的 span 标注、少量案例及程序修正；
按官方描述，它们不提供可直接认定独立的新母来源。
LegalBench [sara_entailment](https://github.com/HazyResearch/legalbench/blob/main/tasks/sara_entailment/README.md)
明确源于 SARA v2；其 277 条任务不是 277 个独立新母来源。上述镜像或改写不能重置暴露。
结论限定于已经核查的公开 release，不断言未来不存在新增来源。

## 建议的主评价安排

SARA 继续保留训练、错误类型、查询 ABI 和程序诊断，不提供“新盲测 SARA”一列。
对其余四库重新冻结，候选规模建议 CNI DEV16/TEST32、Airline16/32、OE16/32；
MAUD 库存不足原16+32，建议改为 DEV8/TEST24，实际按完整隔离组确定。
这是必须明示的评价规模修订，不能把旧 TEST 换名字填满。
新 TEST 全量保留消费者拒绝和域外样本，报告分母及覆盖；不按结果重抽。

## 建议补充：官方 LegalBench diversity_1…6

推荐该系列作为单列的独立外部评价域。它提供当事人身份、州籍、索赔双方与金额等关系，
与本项目的绑定和结构迁移问题直接对应；无需把旧 SARA 变成新题。
它并不替代原研究的税法盲测主张，也不增加本轮模型调用。
官方 [variant1](https://github.com/HazyResearch/legalbench/blob/main/tasks/diversity_1/README.md)
与 [variant6](https://github.com/HazyResearch/legalbench/blob/main/tasks/diversity_6/README.md)
分别给出简单与多方多索赔结构、二分类任务和 CC BY 4.0 许可。
发布者的[固定版本元数据](https://huggingface.co/datasets/nguha/legalbench/blob/b751c0b1d466908abaea041b5cc473a9fb05799f/README.md)
列出每个 variant 的 train6/test300；数量只是官方行数，尚未做项目内源族去重。

具体实施提案如下，需在恢复正式评价前纳入新版协议：

1. 固定官方 release/commit、文件 SHA 和许可；先只导入 metadata。把
   `answer`、`parties_are_diverse`、`aic_is_met` 三列全部封存，后两列同样是标签。
   reader 只看事实文本与官方任务规则。将本轮已查看的 README 示例登记为公开开发材料，
   不将其变体混入 TEST。
2. 新建经过独立单元检查的外部 F，输入 parties(id,side,citizenships) 与
   claims(plaintiff,defendant,amount)，保留 unknown 及未覆盖条件。
   按该 benchmark 公布的简化规则检查异籍和同一原告—被告对的索赔聚合，
   禁止跨当事人对直接求和。完整多原告准入条件必须逐 variant 对齐官方规则，
   不能仅凭一个金额阈值写出貌似完整的消费者。程序与标签映射先于测试冻结。
3. 原五库 TRAIN128 和八批保持原样。外部域另列一个固定小型校准阶段：
   提议 variant1–3 官方 train 共18行，D6/C9/R3；variant4 官方 train6行作为 DEV；
   variant5–6 官方 test 仅按预定 SHA 顺序各选16个完整母来源，最多32个 TEST。
   三列标签由评分端单独保管，角色先于任何输出冻结。若父族／模板去重后不足，
   报告实际数量并停止补抽；不生成改写题填额。此额外校准阶段尚未获正式派发授权。
4. 对名字、金额、排列和同一生成骨架建立联合源族；核对与全部既有项目材料无重合。
   结构族跨 D/C/R/DEV/TEST 的隔离优先于行数。variant 是结构组，
   32行不等于32个新结构，置信区间也不能把重复模板当独立结构样本。
5. 所有七系统得到相同的外部法律程序、规则与预算条件；M2 只能在冻结的 TRAIN
   参考分布上选接口，不读取当前 TEST 真图或弱输出来选。冻结后才统一做原生 Yes/No
   准确率、覆盖／拒绝率、每母来源错误、逐 variant 结果与成本。
   两个中间标签只用于最后一次机制分析，不反哺修复。

选择 diversity 系列的依据是可声明的任务语义、关系结构和评分接口，尚无该数据上的效果观察。
当前没有下载 TEST、生成预测、创建调用队列或启动额外训练。
若采用，论文需要分别呈现“四库新测试 + SARA 已暴露诊断 + 独立外部结构域”，
不能合并成原五库完整新盲测或据此外推税法泛化。
