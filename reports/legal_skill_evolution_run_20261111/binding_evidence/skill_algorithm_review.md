# 技能演化近邻精读及当前 binding-learning 原型复核

日期：2026-11-13。该复核针对冻结前初稿；负例标注和alpha规范化问题已修复，真实结果及后续决定见stage_conclusion.json，本文件不作为执行队列。范围：只读当前两份 docs、报告第11节、实现和原TRAIN公共材料；未改项目、未新增项目模型请求、未读DEV/TEST。本文是研究建议，不是新的执行协议或贡献验收结论。

## 结论与建议

最值得保留的修正方向是**学习源读取中的跨角色绑定操作**，不是继续压缩闭式法律规则，也不是给现有4项技能增加utility reranking。当前 `binding_learning.py` 已经有这个区别：输入是尚有开放槽的真实局部语义片段，输出是决定当前原文中哪些provider共同填入这些槽的可复用策略。它可以在原有ContractNLI TRAIN母合同内验证，不需要新数据、模型参数训练或测试时教师。

这还不是已成立的贡献。其DNF与精确set-cover属于成熟关系学习；“同信息强对照下，更可靠或更低成本地取得跨句法律规则”仍可构成研究贡献，但需要真实跨母合同证据。当前实现最容易被普通joint ILP、nearest-header或自由G吸收。应以现有一次固定小试作决定，不再平行扩充另一套泛化修补/信用分配框架。

## 1. 近期工作到底学什么、如何证明、提升多少

下列均核验官方论文；前四项同时核验作者代码。数字来自注明的论文版本，pp为百分点；整个方法的收益不等于某组件的独立收益。

|工作|实际学习对象及监督|最有辨识力的证据|本任务含义|
|---|---|---|---|
|[MemRL，v1](https://arxiv.org/html/2601.03192v1)|冻结LLM；外部Intent–Experience–Utility记忆；终局环境反馈更新Q，再作语义召回后的utility选择|冻结记忆、30%保留集相对MemP：BigCodeBench .494→.508，OS .720→.746，DB .928→.942，ALFWorld .421→.479。另有同记忆去RL与检索权重消融|证明学习“使用策略”可以有贡献，并不要求更新模型权重；但它是取用记忆，不负责缺失规则获取|
|[MemSkill，v1](https://arxiv.org/html/2602.02474v1)|学抽取/合并/删除的**操作技能**，PPO训练MLP选择器，LLM designer按难例改技能；冻结reader|Llama LoCoMo LJ 50.96，随机controller 45.86、静态skillbank 44.11；ALF unseen 47.01 vs ReadAgent 38.06。消融分开使用策略与技能演化|“学习获取操作而非仅存结果”与当前问题契合；其PPO训练和70B reader不能不加说明地迁入现配置|
|[EvoSkill，v1](https://arxiv.org/html/2603.02766v1)|训练答案和执行反馈给proposer；builder写SKILL.md/脚本；在验证上接纳、保留前沿程序|OfficeQA 60.6→67.9、SealQA 26.6→38.7；全文未找到独立组件消融，不能由整体增益推出特殊更新机制胜过普通程序修补|是强“自由程序/技能更新”基线依据；文件结构和多角色本身不能成为我们的差异|
|[MASkills，v1](https://arxiv.org/html/2609.02094v1)|基于轨迹的语言critic作skill条件反事实归因，层次聚合、momentum、改写/归纳/合并/剪枝及验证回滚|GAIA full 23.3，去credit 17.1，去momentum 21.9，去rollback 13.5；这些是同系统组件消融|泛称“反事实归因+稳定更新”已有直接近邻。官方credit实现是LLM判断反事实，不能说它实际重跑了全部删技能环境|

这些工作没有证明普通程序在表达能力上无法实现它们。可信证据来自：**明确定义学习对象，保持其余信息一致，去掉该学习操作后在实际任务上变差**。因此“普通程序可表达相同逻辑”不是充分否定理由；反之，仅把原程序包成技能也不能证明新贡献。

### 官方代码核验位置

- MemRL：固定提交 `c1b322ca43de36ddf64c6712f89d0095bfc35ce0` 的 [value_driven.py](https://github.com/MemTensor/MemRL/blob/c1b322ca43de36ddf64c6712f89d0095bfc35ce0/memrl/service/value_driven.py) 与 [memory_service.py](https://github.com/MemTensor/MemRL/blob/c1b322ca43de36ddf64c6712f89d0095bfc35ce0/memrl/service/memory_service.py)：前者按reward/Bellman target更新metadata Q，后者从semantic候选归一化Q并混合排名；终局奖励会更新检索到的记忆，不是精确因果credit。
- MemSkill：固定提交 `f65b797338033f4f9c34822f1810f9c2747e6022` 的 [controller.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/controller.py)、[trainer.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py)、[designer.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/designer.py)：真实PPO反传和optimizer.step，不应误称全程无参数学习；designer有尝试、失败记录与rollback。
- EvoSkill：固定提交 `36f6f04952293d7054145550c2b9f0b0411bff1c` 的 [feedback_descent.py](https://github.com/sentient-agi/EvoSkill/blob/36f6f04952293d7054145550c2b9f0b0411bff1c/src/feedback_descent.py) 是proposal/evaluator preference循环、保留失败反馈与early stop；这是广义文本反馈优化，不能当成尚未公开的新机制。
- MASkills：固定提交 `7b72f8b412a5b2143cedc6986261dd06fffe04c1` 的 [skill_credit.py](https://github.com/DaRL-GenAI/MASkills/blob/7b72f8b412a5b2143cedc6986261dd06fffe04c1/maskills/core/skill_credit.py) 向LLM传轨迹和使用技能，再解析其credit；不是实际移除技能后的环境执行差。

### 邻近路线的排除依据

[CaSKG](https://arxiv.org/html/2608.25500v1) 已有文本反事实探针校准技能图边再检索；ALF Skill-1000消融full 73.57 vs semantic-only 67.14、去judge 71.43，但文本探针不是环境因果重跑。作者[代码](https://github.com/ZhiyuanLi218/Caskg)已核验存在。现库没有相应的丰富依赖图，不宜为采用它先制造规模。

[UMEM](https://arxiv.org/html/2602.10652v1) 的语义邻域边际效用和 [MGPO](https://arxiv.org/html/2609.37930v1) 的更新前后同reader反事实credit已覆盖普通“按边际贡献优化记忆”的说法。两者训练memory writer参数；MGPO还使用SciREX结构标注/金实体边界。它们不是现有native终局监督可直接复现的无参数更新。UMEM正式[ICML版本](https://proceedings.mlr.press/v306/ye26j.html)与arXiv v1摘要数字不同，本文不混用版本最大提升；MGPO未核验作者开源代码，不能拿代码可用性作支持。

## 2. 为什么当前不推荐retrieval/utility方向

当前 `artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json` 的实际末态是4个技能，不是所有accepted-create提议的累计数量：Airline一个integer技能，OpenExempt一个object技能，SARA两个string技能。`runtime.py:394 retrieve` 只按答案类型筛选，再作词面相关检索。原TRAIN的公开视图中，OE64个视图、Airline24个视图各仅1项类型合格；SARA24、ContractNLI96、MAUD72各2项，其中后两库对应的仍只是两个税法技能。未读取grading文件作本分析。

因此，现阶段reranking没有丰富的同任务能力候选可学习；ContractNLI/MAUD的关键缺口是没有取得相关读源技能。给4条技能学习utility至多更合理地不调用，无法承担所需新规则获取。不能为建立检索贡献而追加skillbank或换任务。

## 3. 新binding原型的实质与旧路线边界

已读 `legal_skill_guard/skill_evolution/binding_learning.py` 全部代码。其流程为：

1. 由真实获取的fragment给出闭合typed value，或带typed slots的claim；不由host提供法律值。
2. 枚举当前源中类型和显式requires相容的完整provider assignments；同一变量只有一项provider。
3. 从示范学习assignment上的DNF：槽相对claim的同单元、前后、当前标题/同标题关系，以及不同槽provider之间的同单元、同标题、同provider关系。
4. 新源上依策略选择assignment；只有闭合term唯一才产生规则，保存相应原文支持，其他情况保持未决。

这与旧NQG的关键区别是：NQG从已给定源—闭式语义配对归纳组合；此对象要在**新源未闭合的片段**之间学习哪些provider能够联合填槽。它也不等于闭式R投影或普通规则缓存。若实际decoder已通过requires、字段名或原文选择提前指定了唯一正确provider，该差异消失；应按真实输出判定，而非按模块名称判定。

其最近的传统近邻是从填槽标注学习抽取规则的 [RAPIER](https://www.jmlr.org/papers/v4/califf03a.html)、ILP信息抽取，以及 [FlashExtract/PROSE](https://www.microsoft.com/en-us/research/project/prose-framework/tutorial/) 的示例驱动抽取程序合成。因此，不能声称DNF、联合填槽或从示范学抽取本身全新。可以成立的具体假说是：**法律源中共享scope造成的角色间约束，在同信息获取下提高了新源绑定可靠性或降低全部获取成本，而非仅提高native标签命中。**

### 小试前值得修的具体不兼容

- **单一示范ID不自动给出完整负例集。** 当前learn把非示范provider ID组合全标负，而resolve按闭合term合并等价输出。两个不同provider若产生完全相同的term，会出现假负例与学习不可分。相同term本身也不认证不同出处的作用域：不能直接把所有同term组合升为源正确正例。应显式取得完整已核实有效assignment/替代见证，或把未审查组合标未知；输出等价与source-binding正确性分开保存。若教师明确提供完整有效assignment集合，应保存该完整性声明和支持。
- **family依赖slot拼写。** 当前hash包含原样slot名称。可确定性alpha规范化开放变量，保留同一变量的所有重复位置与类型；这是语义保持修复，不能把不同语义角色随意合并。否则真实decoder换个变量名就造成策略不命中。
- **特征表达界限要据实记录。** 当前Boolean特征不能总是区分多个“同标题且在前”的provider；nearest-header还使用距离排序，DNF反而没有相同相对排序信息。出现不可分应记录，不按失败结果追加来源或手工法律谓词。先看真实片段是否存在这种情况，再决定必要实现修正。
- **共指与证据不是joint独占能力。** 类型、重复变量必须同一provider、真实support完整传递应向所有控制开放。不同provider的等价term可保留多份替代见证，不应把这些见证合并成虚构的大证明。

## 4. 最小真实检验与强对照

沿用主执行者已确定的原TRAIN4母合同获取、冻结后固定TRAIN复用计划；不要求新增来源、DEV或TEST，也不要求全分支覆盖。

**共享部分：** 相同真实原文、local-fragment decoder、词义/typed constructor、grounded demonstrations、普通输入修复、P消费者与资源口径。取得fragment语义和demo的教师开销必须计入；共享资产隔离执行作用，不能包装成双方独立端到端获取。自由G需相同信息独立获取，并可自行采用binding架构。

**比较：** joint DNF；同学习器去掉cross-slot关系的independent；强nearest-header（同单元、当前header、距离、保留平局）；同信息自由程序。普通joint ILP/DNF若与当前学习器语言、监督和目标完全相同，本来就是同一个算法，直接标为采用成熟learner，不必为了图表再造第五条等价学习臂。

**真正有辨识力的记录：** 新源真实provider候选有多少、多少存在不同语义可行组合；学到的cross-slot clause实际筛除了什么组合；改变哪个已获取规则与原生判断；错误究竟发生在局部语义、遗漏provider、绑定、consumer还是fallback。报告端到端主路径/源支持正确性与总成本，fallback独列；joint=independent时如实判定本批没有额外联合作用。

d936把“continued bound notwithstanding return”误作return义务，及4607c漏掉“upon demand”，均不能仅通过绑定算法修复。若共同local decoder仍没取得动作/触发语义，必须先记录获取失败；强行分槽不会制造缺失语义。

### 本轮研究决定

推荐完成这一项有限真实binding检验；它比utility检索更贴近已知获取失败，也确有可执行学习对象。若真实材料无需joint、或自由G/nearest达到同等源正确性与成本，则本候选降级为公共获取组件，不继续换术语包装。若joint确有作用，先建立这一项完整贡献，再寻找独立第二瓶颈；目前不能由本研究建议或确定性实现宣布两项贡献通过。
