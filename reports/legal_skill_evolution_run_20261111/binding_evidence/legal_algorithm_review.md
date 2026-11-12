# 法律学习算法定向复核，2026-11-13

## 结论

**本轮没有找到一个既区别于现有强方法、又直接针对当前源获取失败、值得立即实现为新贡献的算法。** LAS/ILASP可作具体规则学习基线；进一步核查发现，联合选择潜在事实和规则的MetaAbd，以及冻结模型下重查事实、重建规则模板的ILP-CoT，已经覆盖“不要让规则补偿错误facts”的主要算法构想。

现有失败主要发生在“原文中的主体、动作、触发和例外怎样共同构成一条规范”。只说联合学习源解释G与规则H仍不够：必须说明超出潜在事实反演、程序归纳、最短一致解释和失败后重抽取的哪一个计算步骤；本轮没有找到可辩护的新增步骤。

这是本轮筛选结论，不是源获取问题不能研究，也不是“通用代码能表达它，所以没有获取价值”。此前共享操作干预不能否定独立获取可靠性。本次普通开放更新中，两方均独立学到新effect构造，开发12/16对11/16、复用各1/4且方法唯一正确项源证明错误，尚未显示方法的独立获取或复用优势；这仍不等于证明一切源获取算法都被吸收。

## 已核对的实际问题

已读CURRENT_GOAL、METHOD_REDESIGN_CURRENT、open_effect_evidence/source_semantic_review.json及根代理补充的existing_evidence_constraint.json。没有读取项目DEV/TEST标签，没有项目模型调用或修改源码。

- d936的49提供主体/模态，50提供返还行动及触发；51是继续保密。现有方法从51产生了错误返还根。删除该根后四个原生答案不变，nda-16 evidence F1从.5到.6667，但仍没有取得49。这说明证据监督有用，也说明单独删根/加F1没有实现缺失关系获取。
- 8af在同一个58跨度中区分了Receiving Party与其legal department/outside counsel；正确出处不自动验证保留权限的主体。当前方法确实把主体扩大。
- bbb390实际行动在78、例外在79–83；方法用75–77标题及未完成句产生义务。4607真实upon demand在32，原G却返回空触发。它们是源识别/绑定问题，不能归到下游求解器、类型或预算。

## 新增法律近邻与实现核对

### 1. XAI-LAW：确实学习新法律规则，但人工形式化在前

[Dovier等，XAI-LAW: A Logic Programming Tool for Modeling, Explaining, and Learning Legal Decisions](https://arxiv.org/html/2601.03844v1)，arXiv 2026-01-07；正文对应ICLP2025工作。

§5的算法以人工编码的判决事实、inclusions/exclusions与context构建ILASP任务，选择规则加入法律库，并用using_judgment区分判决来源。§3对规则过严/过弱的修订包含人工检查。Table1是搜索空间与学习耗时，不是自动文本获取准确率。作者明确把初始自然语言到ASP人工编码列为尚未解决的瓶颈。

已沿[实验室官方入口](https://clp.dimi.uniud.it/sw/)找到并查看[官方ASP/ILASP编码](https://benedettas.github.io/ragionamentolegale/)。当前仓库commit为`ccecc9aac36501717ba01c4c595151129c2ad050`。articoli.html包含显式ASP法条，sentenzeartt581582.html包含已经填好的#pos三元组。它们验证了正文所述输入边界，未提供从合同原文自动取得非局部主体/动作的学习器。

### 2. LLM2LAS：最完整的可移植算法和代码

[Borroto等，Question Answering with LLMs and Learning from Answer Sets](https://www.cambridge.org/core/journals/theory-and-practice-of-logic-programming/article/question-answering-with-llms-and-learning-from-answer-sets/C9B99D67B27C2A8EC6D2D4D00FBEF08C)，2025-11-03 online，TPLP 2026卷期。

§4先由冻结LLM逐句抽fluents和类型，再生成mode bias；答错时，把故事作context、正确/错误回答作partial interpretation，用ILASP重新取得可迁移ASP假设。能自动学习外部程序，不能概括成普通提示。原文§6也指出未显式抽出的概念与假设空间规模问题。

实际查看[官方journal分支](https://github.com/IrfanKareem/llm2las/tree/journal)，commit `865844c5d98c0057e554711936137021ccd240b6`：

- DatasetParser.py:28–53先解析问题、再解析事实，并调用updateFluents/setEventCalculusRepresentation；BasicParser.py:326–387确实写入facts及mode bias，作谓词同义规范化。因此不能说整个系统的facts/bias从不改变。
- ExpressivityChecker.py:45–115把已有EC表示、background及训练答案写成可满足性任务，返回是否需要EC的布尔值；DatasetPipeline.py:56–63据此选择formalism，然后进入训练。这个checker没有调用parse_llm、修改sentence.fluents或按反例重抽取。
- modeBiasGenerator.py:65–112会重新组装bias，包含nnp→nn类型修复、必要时补fluent1/fluent2；这比固定人工mode bias强。它在train开始组装，不是每次答错后做语义重抽取。
- DatasetPipeline.py:82–92只在答错时调用learner。learner.py:272–295累积context/inc/exc、ILASP求解后setHypotheses；450–480逐步扩大literal上限。这个反馈路径更新H/搜索范围，没有回写源抽取器。

OverallPipeline.py:12、25–28的CLI默认Fluent，Fluent/EC均显式绕过自动checker并固定formalism；DatasetPipeline直接调用才默认开启checker。因此准确差别是“前处理会生成和规范facts/bias；所核对训练反馈路径没有修正源语义”，而非笼统facts恒固定。native答案已对但8af主体扩大时不会触发学习。未执行第三方代码。

### 3. 联合事实与规则不是空白：MetaAbd、法律SS-ABL和Safe-ABL

[Dai与Muggleton，Abductive Knowledge Induction from Raw Data](https://www.ijcai.org/proceedings/2021/254)，IJCAI2021，1845–1851；arXiv初稿2020-10-07。§3.1–3.3在同一解释空间中选择H与潜在facts z：要求B∪H∪z蕴涵观察y，以程序复杂度先验乘感知概率评分；H约束z，z的概率也剪枝H，再用反演标签更新感知模型。含递归、谓词发明和后续任务复用，不只是固定KB下修facts。

已查看[官方代码](https://github.com/AbductiveLearning/Meta_Abd)，commit `65263f36b83c5fbf5b7a07acaf0b74e8433b2729`：meta_abd.pl:17–50联合保存best_program/best_abd，prove_aux在同一证明中调用abducible和meta-rules；meta_abd_clp.pl:17–60先归纳约束再best_labels，按联合分数择解。python/learn.py:74–134及183–254将反演标签训练感知器。**原算法有参数更新，但冻结感知分布、只保留联合符号搜索并不产生新的搜索机制。** Table2/3是端到端比较，Fig.3b及App.C/Table4检查归纳/反演效率和meta-rule数量，没有把某个法律源忠实性提升单独归因给联合学习。

[Huang等，Semi-Supervised Abductive Learning and Its Application to Theft Judicial Sentencing](https://www.lamda.nju.edu.cn/huangyx/src/ICDM20-SSABL.pdf)，ICDM2020，DOI10.1109/ICDM50108.2020.00127。Alg.1交替用KB修正抽取pseudo-label、估计KB数值参数θ、重训BERT。§V.B的θ是量刑基数/情节权重，不是从自然语言归纳法条结构。[官方代码](https://github.com/AbductiveLearning/SS-ABL)，commit `57429b68edc5cc5ad4ccfe9b0616dbc2c53c2820`：ss_abl_model.py:258–280反演后sentence.fit；sentence_model.py分别拟合baseline/rate；法条和matching rules另行提供。TableI同BERT/规则下，10%标签时SS-ABL F1 .862、ABL .824、PL .814；不是源编译器组件消融，也不适用于当前冻结模型约束。

[Yang等，Safe Abductive Learning in the Presence of Inaccurate Rules](https://ojs.aaai.org/index.php/AAAI/article/view/29572)，AAAI2024，16361–16369，2024-03-24。正文公式(1)–(3)为可疑规则引入参与反演的概率ω，与感知参数θ联合最大似然更新，再以阈值筛规则。它学习规则选择/可信度，不发明新的源语义关系。其legal dispute Table2同BERT，Safe-ABL micro/macro F1 70.72/66.14，SS-ABL70.48/64.18；差.24/1.96pp，并非大幅源抽取收益。已读作者[完整PDF](https://www.lamda.nju.edu.cn/publication/aaai24yang.pdf)的方法与相关实验；未定位官方代码，不能声称没有代码。

### 4. ILP-CoT：冻结模型也已有facts重检、规则结构重建

[Peng等，Abductive Logical Rule Induction by Bridging Inductive Logic Programming and Multimodal Large Language Models](https://arxiv.org/html/2509.21874v1)，2025-09-26。§3先提capture tokens和facts，把LLM规则提议去语义成meta-rules，由Metagol归纳。§3.5失败后拆开重问facts、更新facts；仍失败则裁剪谓词/重建meta-rules，必要时重采tokens。它覆盖“冻结抽取器+反演/归纳失败驱动源修补”的路线。

[官方实现](https://github.com/future-item/ILP-CoT)，commit `68aa241e56610937d5c2f798c62f21deafe5ad85`：main.py:44–54确实逐个重问正例facts，仅保留回答严格等于Yes的原子，再求解；56–79重新取得正负facts和meta-rules。不是只有论文概括。所读入口未实现§3.5全部20%裁剪细节，prompt.py还有重定义/入口签名不一致，故只能称reference实现，未执行或声称复现。

Table1同Qwen-7B：81.85%对CustomCoT35.85%、Direct51.60%；强预训练NEUMANN97.43%但感知监督不同。Table2 Metagol81.85、Popper46.74、ILASP五分钟超时，比较同时改变结构bias/后端。App.B/Table7缺失facts修复率.133–.462、错误facts1.0是按错误类型统计，**不是移除reflection的因果消融**。没有找到单独“重查facts”对照，不能把全增益归给它。

### 5. OblEx26：直接研究非局部义务连接，但依赖结构标注和参数训练

[Moore等，OblEx26](https://aclanthology.org/2026.nllp-1.4.pdf)，NLLP，2026-10-28。

§5.2.2使用共享ModernBERT、组件分类head及最多16义务的membership linking head，交叉熵/BCE联合训练，梯度更新backbone。它允许组件属于多个义务；训练中按首次文本出现排序义务，处理置换。Table5 joint detect+link的soft F1=.264；强结果来自微调SLM，不能归给连接头。高quote anchoring也不等于关系正确。

已查看[官方资源库](https://github.com/pjm56/oblex26)：当前列出的资源是标注指南和测试数据压缩包，未发现训练/linker源码；未打开测试数据。不能把论文算法说成现成的冻结模型源绑定学习器，也不能为了移植它新增我们的组件标签或改为参数训练。

### 6. 两项容易被误用的近邻

[Horner等DDL扩展版](https://arxiv.org/html/2506.08899v3)，2025-12-31 v3：§4.2分别试过完整历史、旧atoms、一次处理全部snippets。共享atoms会被用于错误情境，多snippet会合并细节；§4.4.2的改进仍是LLM refinement。它支持问题存在，但不提供新的外部获取器学习算法。读了完整方法、相关实验与提示；未定位作者代码链接。

[LRI/SILVER](https://arxiv.org/html/2505.14104v1)，2025-05-20：Alg.1及App.C.4用多数案例支持阈值验规则，再诱导未覆盖规则。[官方库](https://github.com/HKUST-KnowComp/Legal-Rule-Induction)当前包含data和README，非学习器代码。其相似判例集合预设共享法理；本项目不同合同合法采用不同规则，不能对其作多数规则投票，也不能把Airline的24案例当24独立法源。

## 一项具体算法：LAS源绑定学习，为何目前只能列为基线

最接近实际缺口、能够写出完整计算过程的移植如下。这里明确给出，以便判断差别，不将它直接列作新方法。

1. 从完整原文取得候选局部语义及位置集合，保留来源和未决项。由这些对象生成有限mode bias；不能把已核查的49/78/例外连接手填进方法。
2. 每份原TRAIN来源形成context；原生答案生成inc/exc约束，已有原生evidence形成支持集合约束。
3. 学习ASP关系程序H，使它在各context中推导norm的主体、动作、触发及例外连接，再交给同一个消费者P。学习结果是外部程序，无神经参数更新。
4. 每遇新训练来源，累积约束并用ILASP增量求最短一致H；冻结后在后续原TRAIN源使用。

其关键机制是“从所有来源的语义约束联合求关系程序”，不同于逐份教师自由写G。但**这正是ILP/LAS的直接应用**。若把词项、scope、guard和节点发明交给教师，再让ILASP选出满足约束的版本，就落回已核查的普通候选搜索。尚无额外算法可归于我们。

更实质的限制是：若上游候选根本没有49的主体/模态，H缺少可连接输入；若候选已有完整关系，普通LAS或同信息全局约束求解就已经能做。提高evidence权重可以要求覆盖49，却不自动决定49里的哪一项是该义务主体。若为此新增人工角色标签，改变了监督；若仍由教师判断，则强对照也必须得到同一判断。不能把该信息优势误算作新学习算法。

这不是“不可能学”的定理。原文和冻结语言模型的先验仍包含语义信息。这里的判断是：本轮没有找到一个新的、明确改变如何利用这些信息的学习过程。

## 对“联合G/H避免规则补偿facts”的最终判定

**该总构想已被覆盖；建议停止把joint作为候选名称或主要差别。** MetaAbd甚至直接讨论同一观察可被错误z加错误H共同解释的耦合问题；它不是只在固定正确facts上学规则。ILP-CoT则覆盖参数冻结后重查facts与重建H空间。把神经感知器换成外部G、把digit换成actor，并不足以形成新增算法。

本任务必须区分两个共享层次：源内有效规范H_d随合同/政策d变化，可共享的是解释源文本的G。联合搜索应有独立的z_d/H_d和显式source身份，只有G的语言/结构操作跨来源复用；禁止把互不相同的合同规范按多数判真。简单加入source参数与分层变量就能使普通联合反演适配这个条件，因此“文档之间法律效力不同”本身也不是它无法满足的假设。

真正破坏常见成功假设的现材是**监督不足以区分事实错误与规则错误**：d936删51后4答案不变；8af主体扩大仍native正确；bbb390的错根也能给对标签。原生y只约束结果，不识别中间解释。已有CNLI evidence能增加支持集合信息，仍未逐项指定actor/action/trigger的真实连接。MetaAbd的复杂度与感知先验只是在多个可行解释中选择，并不保证法律源忠实。给候选也加相同先验/证据约束后，这个问题仍存在；不能把它描述成只有近邻遭遇而我们已解决。

能吸收当前joint想法的**最强普通控制**是文档分层的反演+ILP/MaxSAT：保持同一候选源语义集合、同一G程序空间及同一消费者，联合选择每份z_d/H_d与共享G，优化相同原生答案损失、已有evidence约束、解释/程序复杂度和修改代价；允许丢弃错误原子，也允许增量调用与ILP-CoT相同的信息来重查/补出缺失候选。每份H_d始终在本source内生效。它不需要新神经参数，不只是固定facts后ILASP，也不是把source正确性交给方法独占的teacher。若候选的新计算步骤与它产生同一个可行集、同一个目标或等价搜索，就是这一普通控制的实现。

与旧M2误读通道的差别必须落实为更新算法：旧通道已有“源读错导致规则错”的对象；最近source-feedback开放更新又已允许修G/P。将两者的变量放进同一个loss/循环，没有超出这两条基础能力。当前typed grammar若提供同一候选空间，joint只增加标准潜变量选择；若typed grammar原来没有被消费，启用它也只是补齐实现。本轮没有发现新的归因/搜索/复用算子，足以与上述强控制分离。

## 与旧方案的差别逐项判断

|旧对象|LAS移植实际新增什么|为什么还不能算新的源获取贡献|
|---|---|---|
|A完成性分离/选批|从例子学规则，而非选择待补观察|不解决观察/关系本身从原文取得的问题；不能把“solver判未完成再读”恢复成A|
|B学习连接图|可改变推理关系程序，而非重现已知共享变量连接|若原IR已给正确键，仍被普通统一/连接吸收；不能人工抹键制造需求|
|确定性M1 scope/order恢复、M2数值等价/最小反例|本轮没有数值oracle或聚合目标|OE逐资产原生任务不能被改成跨资产聚合来接入它们|
|结构监督M1/M2|LAS不训练共享内容/角色差分模型或四格交互head|现五库没有沿用NormBench完整结构gold；不能假定已有该监督|
|当前typed grammar/继承scope|H若真参与执行，会成为外部关系程序|让原先未消费的文法开始消费是实现改变；仅此不能建立超过普通文法/ILP的机制增量|
|普通开放G/P更新|把教师任意改程序换成显式假设空间的联合求解|这是明确算法对照，但目前增量来自搜索限制/求解方式，没有新的源监督利用或绑定机制|

## 最强简单对照与决定性最小检验

若后续仍选LAS移植，其最近强对照应是上述**同一候选表示、同一全部原文/原生答案/已有evidence、同一推理语义的联合反演+ILP/MaxSAT**，再加已有独立开放G/P更新。开放对照允许同样分解、guard、新节点、历史记忆、联合编辑及相当资源。source_semantic_review是本轮诊断材料，不默认转化为额外actor/role训练标签；若另获授权把现有审查用于反馈，双方应得到同一内容。不能把未取得的关系只提供给方法。独立获取与共享G后的执行控制分别核算。

当前不建议派发新的教师轮次去“验证LAS是否能修d936”。这会把已暴露的诊断来源再次修好，却不验证新增算法。

如要决定是否值得开发LAS适配，最小检验是**先做现有材料上的表示与信号核对，之后才安排真实学习比较**：

1. 仅检查已保存的TRAIN源候选与原生evidence：49主体/模态、非相邻行动及例外是否实际存在为可学习关系；分别记录“缺候选”“有候选无正确连接”。不运行新模型，不把补入的人工连接算学习。
2. 对候选已存在的部分，比较普通LAS与任何拟议新算法得到的约束、可行解和代价。若完全相同，直接归为相同学习算法，不再派发真实调用。不能用另一种搜索语法宣布新能力。
3. 只有在提出了约束、更新或搜索的具体新增步骤后，才固定一个后续未参与该步骤修补的原TRAIN来源序列：双方独立学习同一完整任务，报告实际补出的源绑定、原生行为及全部获取费用。source review用于判定使用的关系是否成立；不以native正确替代。关闭新增步骤的消融必须仍能执行。

第1步是适配前提核对，第2步是算法等价检查，第3步才是决定性方法实验。若只验证joint相对fixed-facts是否有用，最小比较是同一source候选和原生反馈下固定z/固定H/联合三条件；它检验联合优化价值，不能建立相对MetaAbd/ILP-CoT的新颖性。无新增步骤时，不建议实现后再以一次小修补寻找故事。**本轮交付的是核查充分的强基线及未解决环节，没有推荐可直接命名为新贡献的算法。**

## 阅读收据

- LLM2LAS learner.py SHA-256：`0db5ff8bf322bf8a098f977762f37dee5fcdef843cf8824d24b2957584cc2530`。
- LLM2LAS DatasetPipeline.py：`a16c412a2a31ffb4a2e797b0ee38bcbeb9b1a0bfa0f79a8ccc2cb7c2132bd307`。
- XAI-LAW articoli.html：`d8f876d2b67cef1d55535b31a30f9df311b8be1fdbc800d5e98ffd67e0ed4757`。
- XAI-LAW sentenzeartt581582.html：`616e4db617dcbcf157dc0f26c6f455d4824f4d731f53878b96803f5a13519480`。
- MetaAbd meta_abd.pl：`5f15d11c3941a5eec3ce4033209bfa2b88b3dd8055a512b2e85cbbef60363868`。
- MetaAbd meta_abd_clp.pl：`81fd557d7e20577b3a29a1b83b66941295825fc2082926b4c677560e40f673e1`。
- ILP-CoT main.py：`273a09e8d7cca575594ce57cefff14006bff3b104154f0bad48fab389f588ed0`。
- 仅下载/读取第三方材料，没有执行其模型、solver或训练代码；没有改项目文件、Goal或账本。
