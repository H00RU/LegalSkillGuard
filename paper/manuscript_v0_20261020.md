# Evolving Reusable Skills for Legal Rule Application with a Frozen 8B Language Model

中文暂题：面向冻结8B语言模型法律规则适用的可演化技能学习

工作初稿 v0，2026-10-20。这是实际写作起点，不是已完成实验的投稿稿。英文与中文对应；方法以正在运行的v11为准，尚未部署的v12单列。标题不预设优越性，方法名称、最终贡献和投稿期刊尚未确定。内部证据和缺口见[写作证据表](evidence_and_completion_20261020.md)。

## Abstract / 摘要

Reusable skills provide an external learning interface for language models whose parameters remain fixed. In legal rule application, useful experience must specify both when a rule applies and how its consequences are computed. We study batchwise skill evolution for a frozen 8B language model using exemption classification and valuation tasks from OpenExempt. The current implementation represents skills as task-scoped procedural guidance and, for valuation, reusable arithmetic programs associated with statutory citations. The model selects applicable provisions from the supplied facts and statutes; an interpreter evaluates its numerical plan without choosing provisions or repairing predictions. After a batch has been answered, a teacher receives released training feedback and proposes library edits, which are replayed on seen training sources before publication. The evaluation separates static legal priors, online learning, and arithmetic-interface effects through frozen-library and empty-library controls. [PENDING RESULT — subsequent-source and held-out effects against strong controls and adaptive-memory baselines, estimates, 95% CIs, independent n.] [PENDING CONCLUSION — delimit the supported benefit and transfer scope after confirmatory experiments.]

可复用技能为参数冻结的语言模型提供了一种外部学习接口。在法律规则适用中，有用的经验既要说明规则在何种情况下适用，也要说明如何计算其法律后果。本文研究冻结8B语言模型在OpenExempt豁免分类与豁免估值任务上的分批技能进化。当前实现将技能表示为按任务限定的程序性指导，并在估值任务中加入与法条关联的可复用算术程序。模型根据给定事实和法律选择适用法条，解释器只执行数值计划，不替模型选择法条或修正预测。每批回答完成后，教师接收已释放的训练反馈并提出技能库编辑，候选在已见训练来源上重放后决定是否发布。实验通过冻结技能库和空库对照区分静态法律先验、在线学习与算术接口的作用。[待填结果：后续新来源及隔离测试上相对强对照和自适应经验基线的效果、置信区间与独立样本量。][待填结论：正式实验支持的收益与迁移边界。]

## 1. Introduction / 引言初稿

External skill libraries allow a frozen language model to reuse procedural knowledge across tasks. An evolving playbook changes what the model can consult while keeping its underlying weights fixed. ACE studies context adaptation through generation, reflection, and curation [2]. The question in this work is narrower: can experience accumulated over successive batches improve a small model's application of legal rules to previously unanswered cases, beyond the gains from a static legal prior or additional computational support?

Legal exemption reasoning offers a setting in which factual eligibility and numerical consequences can be assessed separately. OpenExempt generates problems from symbolic representations of federal and state exemption law and supplies machine-computable reference solutions [1]. We study two of its tasks. Exemption classification requires identifying applicable provisions for each asset. Exemption valuation additionally requires calculating the protectable amount under each applicable provision. These tasks permit error analysis of asset grounding, statutory selection, and numerical execution; they do not evaluate real-client consultation or the full practice of legal advice.

A convincing skill-learning result requires more than a larger library or an improved replay score. A static prior can outperform an empty prompt before any experience is collected. An arithmetic interpreter can change performance independently of learning. A candidate can also improve a training average while damaging other legal contexts. We therefore distinguish first-encounter performance, post-update training replay, and final frozen-library testing. We also inspect which edits are actually published and which learned operations are actually invoked.

The current research hypothesis is that controlling the scope of reusable edits can improve the transfer of training experience while limiting interference between legal contexts. Scope-conditioned replay and source preservation are already studied in SkillCommit [3]; these ideas alone are not a novelty claim. Our prospective scope-level implementation is described separately below. [PENDING ANALYSIS — identify a defensible methodological contribution and its nearest-neighbour differences, supported by ablations and new-source outcomes.] [PENDING RESULT — replace this placeholder with the main empirical finding, rather than a promised outcome.]

外部技能库让参数冻结的语言模型能够跨任务复用程序性知识。技能库的进化改变模型可以利用的经验，而不更新其权重。ACE通过生成、反思和策展研究上下文适应[2]。本文关注更具体的问题：连续批次积累的经验，能否让小模型更好地将法律规则应用于此前未回答的案件，并产生超出静态法律先验和额外计算支持的收益？

法律资产豁免任务允许分别检验事实适用与数值后果。OpenExempt基于联邦及州豁免法律的符号表示生成问题，并提供可计算的参考答案[1]。本文研究其中的豁免分类和豁免估值：前者要求为每项资产识别全部适用法条，后者还要求计算每项适用豁免的可保护金额。因此可以分别分析资产事实对齐、法条选择和数值执行错误。这不是多轮客户咨询，也不等价于评估现实法律服务能力。

可信的技能学习结果不能只看技能库变大或训练重答得分提高。静态先验可能在学习开始前就胜过空库；算术解释器可能独立影响成绩；候选也可能在训练平均分上获益，却损害其他法律范围。因此本文区分首次遇案表现、更新后的训练重放和最终冻结库测试，并检查实际发布的编辑与实际执行的技能程序。

当前待验证假设是：约束可复用编辑的作用范围，有助于训练经验迁移并减少不同法律情境间的干扰。作用域重放与来源行为保持已有SkillCommit等工作研究[3]，不能直接作为本文原创。下文将尚未部署的作用域提交实现单独说明。[待填分析：以消融和新案结果确定可辩护的方法差异。][待填结果：正式实验支持的核心发现。]

## 2. Task and data / 任务与数据

**Task definition.** For each source case, the actor receives the task's public facts, statutes, and supplied solved steps. In the current configuration, allowable exemption jurisdictions are given; the actor is not asked to re-solve the preceding jurisdiction-selection task. EC returns a mapping from asset descriptions to applicable statutory citations. EV returns the corresponding citation–amount claims. EC and EV share an underlying source case, although their natural-language fact renderings need not be identical. They are correlated task views, not two independent datasets.

**Data provenance.** Development cases are generated with the unmodified OpenExempt generator, pinned at commit `ec6fa2547431096588ce2d3ef107b8adc33cd4fe` [1]. The current mechanism run has 32 source cases, divided into four batches of eight, with both EC and EV tasks for each source. Generation settings specify two to four assets, a married-case ratio of 0.5, and state jurisdictions Arizona, Illinois, Oregon, Pennsylvania, and Wisconsin. Federal provisions can also appear in the public allowable framework. These 32 generated sources are development data, not the complete 9,765-sample benchmark or a formal held-out evaluation.

**Information boundary.** All four current control/treatment predictions for a batch are recorded before that batch's targets are released for grading and learning. The teacher can access released training targets, but neither actor nor teacher receives private symbolic construction fields as an inference tool. The benchmark solver is used for data construction and target generation, not as an actor tool. No separate validation set is used: seen-source replay is part of training optimization. Previously inspected sources remain development/training data and cannot later be relabelled as held-out test data.

**任务定义。** 律师执行器接收任务公开事实、法律和题目给定的前序解答。当前配置已给出可选豁免法域，不要求模型重新求解前序法域识别任务。EC输出资产描述到全部适用法条的映射；EV进一步输出法条与金额。EC和EV来自同一底层来源案件，但自然语言事实表述不必逐字相同，不能算成两个独立数据集。

**数据来源。** 开发数据使用未修改的OpenExempt生成器，固定版本为上述提交[1]。当前机制试跑包含32来源、四批、每批8来源，每来源各有EC和EV任务。生成设置为每案2至4项资产、已婚比例0.5，州范围覆盖亚利桑那、伊利诺伊、俄勒冈、宾夕法尼亚和威斯康星；给定框架中也可包含联邦豁免。当前32来源是开发数据，不是完整9,765题基准，也不是正式隔离测试。

**信息边界。** 每批四个对照或处理条件的预测全部保存后，才释放本批标签用于评分和学习。教师可以读取已释放训练答案，但律师和教师不能将私有符号字段作为推理工具。基准求解器只用于数据构建与生成标签，不是律师工具。不另设验证集，已见来源重放属于训练优化。被反复审查过的来源始终保留训练或开发身份，不能改名为隔离测试。

## 3. Current implemented method / 当前已部署方法

### 3.1 Frozen actor and skill execution / 冻结执行器与技能执行

The actor is Qwen3-8B at model revision `b968826d9c46dd6066d109eabc6255188de91218`; its weights remain fixed throughout the current run. Skills carry public legal scope and EC/EV-specific guidance. Relevant guidance is delivered using the supplied public task and allowable jurisdictions, not hidden target annotations. For EV, a stored operation associates one statutory citation with a reusable ceiling expression. The model selects a citation and either calls its published routine or supplies an inline expression for an uncovered citation. The routine body is executed by the interpreter rather than displayed as a formula to copy. Empty-library actors can express the same arithmetic inline.

The interpreter evaluates the submitted asset value and expression. It does not verify factual truth, choose legal eligibility, insert missing claims, or rewrite asset names. Thus a wrong statute, a copied wrong value, or an invalid expression remains an actual prediction error. Public citation labels encode the supplied legal vocabulary, not which provisions apply to an asset. All library metadata and program bodies count toward the current 4,096-token library cap.

执行器为固定上述版本的Qwen3-8B，运行中不更新权重。技能具有公开法律范围以及EC/EV各自的指导；投递依据公开任务和已给定法域，不使用隐藏答案。EV存储程序将法条关联到可复用的上限表达式。模型选择法条后，对已有程序发起调用，对没有程序的法条自行填写表达式。程序体由解释器执行，不作为公式让模型照抄；空库也拥有表达相同内联算式的能力。

解释器执行模型提交的资产价值与算式，不核验事实真伪、不判断适用性、不补漏法条、不改写资产名称。错误法条、错误数值或非法算式均保留为真实错误。公开标签只编码给定法律词表，不透露资产适用答案。当前4,096-token上限计算完整库，包括元数据和程序体。

### 3.2 Teacher updates and publication / 教师更新与发布

After first-encounter predictions are recorded, the teacher receives the released training targets, actual responses, scores, execution information, and library state. The current teacher is `gpt-5.6-sol` with high reasoning effort. It can propose create, update, merge, or delete operations, with at most two candidate attempts per batch. The current packet provides all current sources and a bounded selection of historical evidence to the teacher; admission nevertheless replays all seen training sources, not just that communication subset.

The deployed v11 policy considers EC and EV edits separately. A task-specific edit must preserve that task's original F1 on current and prior sources and improve its current-source endpoint; EV additionally preserves full-output F1. Accepted task changes are composed into one library. Publication requires the composed library to fit the total cap, reproduce already observed native model requests where response reuse is claimed, and pass the unchanged full acceptance rule. Reused responses are decoded and executed under the actual candidate library; stored numerical answers are not substituted for execution. The gate constrains training replay averages, not every case or future-case performance.

本批首次预测完成后，教师获得已释放训练答案、实际回答、分数、执行信息和当前库。当前教师为`gpt-5.6-sol`，high推理强度；每批至多两次候选尝试，支持创建、更新、合并和删除。教师通信覆盖全部本批来源及有界历史证据，但准入仍重放全部已见训练来源，而不是只重放通信子集。

已部署v11分别考虑EC和EV编辑。任务编辑须在当前和历史来源保持该任务原F1，并改善本批端点；EV还须保持完整输出F1。通过的编辑组合为一个技能库。组合库须满足完整容量限制，对声称复用的回答保持实际原生请求一致，并通过未修改的完整准入函数。复用回答仍在实际新库下重新解码和执行，不以缓存数值答案替代执行。该门槛约束训练重放均值，不保证每案或未来新案不下降。

### 3.3 Prospective scope-level variant, not yet deployed / 未部署的作用域变体

An isolated v12 implementation refines the publication unit using legal scopes jointly visible in public contexts. Co-visible jurisdictions, scope moves, and changed shared guidance establish dependencies; connected components define edits that must be assessed together for each task. Accepted components form a single library, followed by the original whole-library gate. This implementation has passed code-level checks and a retrospective replay using released B1 artifacts. It has not yet produced a prospective learning curve or a held-out result and is not the method running in v11. Its use in a final manuscript depends on a separately frozen experiment and evidence of benefit beyond existing scope/replay methods [3].

隔离实现v12将发布粒度细化为公开法律情境中的作用域依赖。同一情境可共同出现的法域、范围移动和共享指导修改建立依赖，各任务的连通分量定义必须共同评估的编辑。通过的分量组成一个库，再经过原完整门槛。该实现完成代码级检查及已释放B1上的回顾性重放，但尚无前瞻学习曲线或隔离测试结果，也不是当前v11正在运行的方法。是否进入最终论文，取决于另行冻结的实验及相对已有作用域与重放方法的实际增益[3]。

## 4. Evaluation / 评价设计

**Endpoints.** EC and EV use the pinned original OpenExempt evaluator. EC measures citation-set agreement after its asset matching. EV additionally requires a citation–amount match under the upstream numerical tolerance. The implementation first obtains native per-case scores and then averages them separately by task. These are not the evidence-extraction F1 scores of the project's earlier ContractNLI experiments. The upstream scorer can ignore claims on unmatched extra predicted assets; a separately labelled full-output EV endpoint counts all predicted claims using the same claim-matching rule. It is calculated within case and then averaged across cases, rather than pooled across all cases.

**Controls and estimands.** The current development run compares an inline-program empty library, a direct-numeric empty library, the fixed initial library, and the evolving library. Evolving versus fixed-initial performance addresses added online learning beyond the shared prior; evolving versus program-empty performance controls arithmetic expressivity; the direct-numeric condition tests whether the imposed program interface underperforms a simpler strong control. It is not an identical-interface comparison. B1, where evolving and initial libraries are equal, cannot establish an online-learning effect.

**Mechanism and cost.** Each batch should report source counts; first-encounter scores; paired gains and harms; proposed, rejected, and published edits; parent/child hashes; library size and tokens; actual program calls; invalid responses; physical model calls; teacher attempts and tokens; and wall-clock time. Logical control predictions that share an exactly identical native request are not independent samples. More skills, more calls, or more successful training gates do not themselves demonstrate useful learning.

**Confirmatory work not yet frozen.** A formal evaluation still requires a predeclared source-disjoint train/test design and sample sizes, independently repeated learning runs, a faithful adaptive-memory baseline, cost-aware comparisons, and source-level uncertainty. The ACE runner is implemented in isolation but has not completed a real baseline run. The primary contrast, aggregation, CI/test procedure, multiplicity handling, and stopping rules for that formal experiment must be frozen before accessing its outcomes. The final test uses a frozen method and library; test results must not be used for further library selection.

**指标。** EC和EV采用固定版本的原OpenExempt评分器。EC按资产匹配后的法条集合计分；EV还要求法条与金额满足上游匹配及数值容差。先计算原单案分数，再分别按任务取均值。这不是项目早期ContractNLI的依据抽取F1。原评分器可能忽略无法匹配的额外预测资产，因此另列完整输出EV指标，按相同主张匹配规则计入全部预测；先在案内计算，再跨案平均，不将所有案件直接汇总成一个微平均。

**对照。** 当前开发试跑包含内联程序空库、直接数值空库、固定初始库与进化库。进化库对比固定初库用于识别共享先验以外的在线收益；对比程序空库用于控制算术表达能力；直接数值空库检查程序接口是否反而不如简单强对照，但不是完全相同接口。B1两库相同，不能证明在线进化。

**机制与成本。** 每批记录真实来源、首次表现、配对收益与损害、候选与拒绝及发布编辑、父子hash、库规模和token、实际程序调用、非法回答、物理调用、教师消耗与墙钟时间。精确请求复用不是独立重复。技能多、调用多、训练准入通过均不能单独证明有效学习。

**尚未冻结的正式实验。** 仍需事前确定来源隔离与样本量、独立学习重复、忠实经验基线、成本对照和来源级不确定性。ACE完整运行器已隔离实现，但未完成真实对比。正式实验的主比较、聚合、置信区间与检验、多重比较及停止规则须在查看结果前冻结。最终测试冻结方法和库，不能据测试结果继续选库。

## 5. Results / 结果

[PENDING RESULT — formal primary EC/EV and full-output EV table; method versus frozen initial, matched program-empty, strong direct-empty, and adaptive-memory baselines; estimates, 95% CIs, independent source n, completed/planned/invalid counts.]

[PENDING RESULT — batchwise first-encounter paired differences and cumulative differences; separate training replay; all learning repeats, publication events, and harmful-case frequencies.]

[PENDING ANALYSIS — scope-level versus task-level/whole-library admission, guidance/program effects, skill-use evidence, legal-context transfer, and full compute costs.]

正式结果待填。当前B1/B2开发得分仅进入内部证据表，不填入正式主表，不从旧实验拼接曲线。

## 6. Discussion and scope / 讨论与边界

The present setup studies synthetic statutory-rule application in the exemption domain with supplied laws and allowable jurisdictions. It does not establish competence on Chinese law, open-world legal retrieval, real-client advice, or broad legal reasoning. Replay-based preservation is a training property and need not generalize to unseen cases. The final discussion must examine negative transfer, teacher supervision and cost, template dependence, benchmark-scoring limitations, and the difference between executable numerical support and improved legal selection. [PENDING RESULT — conclusions warranted by the completed formal study.]

当前范围是给定法律与可选法域下、豁免领域的合成法律适用，不证明中国法、开放法律检索、真实咨询或广泛法律推理能力。重放保持是训练性质，不保证新案。最终讨论必须解释负迁移、教师监督与成本、模板依赖、评分局限，以及数值执行辅助和法律选择能力提高的区别。[待正式结果形成结论。]

## References / 已核实参考来源

1. Servantez, S., Lawsky, S. B., Jain, R., Linna Jr., D. W., and Hammond, K. (2026). *OpenExempt: A Diagnostic Benchmark for Legal Reasoning and a Framework for Creating Custom Benchmarks on Demand*. [Paper](https://arxiv.org/abs/2601.13183); [author repository](https://github.com/servantez/OpenExempt). Dataset, generator, evaluator, and symbolic targets are upstream contributions, not ours.
2. Zhang, Q., et al. (2025; revised 2026). *Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models*. [arXiv v3](https://arxiv.org/abs/2510.04618v3). Native generation/reflection/curation is a comparison target; no completed comparison is claimed here.
3. He, Y., and Yang, W. (2026). *SkillCommit: Evolving Agent Skills through Behaviorally Validated Scope Expansion*. [arXiv v2](https://arxiv.org/html/2608.15165v2). Closest-neighbour scope/replay contributions must be credited and distinguished before a novelty claim.

当前仅核实上述与本稿直接关联的来源，不声称已经完成相关工作综述；模型卡、完整基线与其余必要文献待逐项补齐。没有编造引用、统计显著性、理论保证或发布链接。
