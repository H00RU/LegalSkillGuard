# Evolving Reusable Skills for Legal Rule Application with a Frozen 8B Language Model

中文暂题：面向冻结8B语言模型法律规则适用的可演化技能学习

工作初稿 v0.1，2026-10-20 18:42。保留原文件名便于续接，旧v0已存Git和双盘。这不是已完成实验的投稿稿。英文与中文对应，方法同步已部署的v13直接作答与作用域提交，不再描述旧算式执行方案。标题不预设优越性，方法名称、最终贡献和投稿期刊尚未确定。内部证据和缺口见[写作证据表](evidence_and_completion_20261020.md)。

## Abstract / 摘要

Reusable skills provide an external learning interface for language models whose parameters remain fixed. In legal rule application, useful experience must specify both when a rule applies and how its consequences are computed. We study batchwise skill evolution for a frozen 8B language model using exemption classification and valuation tasks from OpenExempt. Skills encode factual conditions, applicable provisions, exceptions, and necessary numerical reasoning as concise procedural text. The model directly predicts asset-specific citations and amounts through the same answer interface as the empty-library control. After a batch has been answered, a teacher receives released training feedback and proposes library edits. Publicly co-visible legal contexts determine which edits must be assessed together, and accepted components form one library after replay on seen training sources. The evaluation distinguishes subsequent-case performance from training replay and compares learned skills with strong empty-library and adaptive-memory controls. [PENDING RESULT — subsequent-source and held-out effects, estimates, 95% CIs, independent n.] [PENDING CONCLUSION — delimit the supported benefit and transfer scope after confirmatory experiments.]

可复用技能为参数冻结的语言模型提供了一种外部学习接口。在法律规则适用中，有用的经验既要说明规则在何种情况下适用，也要说明如何计算其法律后果。本文研究冻结8B语言模型在OpenExempt豁免分类与豁免估值任务上的分批技能进化。技能用简洁的程序性文本表达事实条件、适用法条、例外和必要的金额推理。模型通过与空库对照相同的回答接口，直接预测各资产的法条与金额。每批回答完成后，教师接收已释放训练反馈并提出技能库编辑。公开法律情境的共同可见关系决定哪些编辑必须共同评估，通过的分量经已见训练来源重放后组成一个库。评价区分后续新案表现与训练重放，并与强空库和自适应经验方法比较。[待填结果：后续新来源及隔离测试效果、置信区间与独立样本量。][待填结论：正式实验支持的收益与迁移边界。]

## 1. Introduction / 引言初稿

External skill libraries allow a frozen language model to reuse procedural knowledge across tasks. An evolving playbook changes what the model can consult while keeping its underlying weights fixed. ACE studies context adaptation through generation, reflection, and curation [2]. The question in this work is narrower: can experience accumulated over successive batches improve a small model's application of legal rules to previously unanswered cases, beyond the gains from a static legal prior or additional computational support?

Legal exemption reasoning offers a setting in which factual eligibility and numerical consequences can be assessed separately. OpenExempt generates problems from symbolic representations of federal and state exemption law and supplies machine-computable reference solutions [1]. We study two of its tasks. Exemption classification requires identifying applicable provisions for each asset. Exemption valuation additionally requires calculating the protectable amount under each applicable provision. These tasks permit error analysis of asset grounding, statutory selection, and numerical execution; they do not evaluate real-client consultation or the full practice of legal advice.

A convincing skill-learning result requires more than a larger library or an improved replay score. A static prior can outperform an empty prompt before any experience is collected, and changing the answer interface can affect performance independently of learning. A candidate can also improve a training average while damaging other legal contexts. We therefore distinguish first-encounter performance, post-update training replay, and final frozen-library testing. We inspect which edits are published and which guidance reaches each subsequent case under a shared answer interface.

The current research hypothesis is that controlling the scope of reusable edits can improve the transfer of training experience while limiting interference between legal contexts. Scope-conditioned replay and source preservation are already studied in SkillCommit [3]; these ideas alone are not a novelty claim. The deployed implementation uses dependencies derived from publicly supplied legal contexts and retains the model's direct answer format. [PENDING ANALYSIS — identify a defensible methodological contribution and its nearest-neighbour differences, supported by ablations and new-source outcomes.] [PENDING RESULT — replace this placeholder with the main empirical finding, rather than a promised outcome.]

外部技能库让参数冻结的语言模型能够跨任务复用程序性知识。技能库的进化改变模型可以利用的经验，而不更新其权重。ACE通过生成、反思和策展研究上下文适应[2]。本文关注更具体的问题：连续批次积累的经验，能否让小模型更好地将法律规则应用于此前未回答的案件，并产生超出静态法律先验和额外计算支持的收益？

法律资产豁免任务允许分别检验事实适用与数值后果。OpenExempt基于联邦及州豁免法律的符号表示生成问题，并提供可计算的参考答案[1]。本文研究其中的豁免分类和豁免估值：前者要求为每项资产识别全部适用法条，后者还要求计算每项适用豁免的可保护金额。因此可以分别分析资产事实对齐、法条选择和数值执行错误。这不是多轮客户咨询，也不等价于评估现实法律服务能力。

可信的技能学习结果不能只看技能库变大或训练重答得分提高。静态先验可能在学习开始前就胜过空库，回答接口改变也可能独立影响成绩；候选也可能在训练平均分上获益，却损害其他法律范围。因此本文区分首次遇案表现、更新后的训练重放和最终冻结库测试，并在共享回答接口下检查实际发布的编辑和后续案件收到的指导。

当前待验证假设是：约束可复用编辑的作用范围，有助于训练经验迁移并减少不同法律情境间的干扰。作用域重放与来源行为保持已有SkillCommit等工作研究[3]，不能直接作为本文原创。已部署实现从公开给定的法律情境建立编辑依赖，并保留模型的直接回答格式。[待填分析：以消融和新案结果确定可辩护的方法差异。][待填结果：正式实验支持的核心发现。]

## 2. Task and data / 任务与数据

**Task definition.** For each source case, the actor receives the task's public facts, statutes, and supplied solved steps. In the current configuration, allowable exemption jurisdictions are given; the actor is not asked to re-solve the preceding jurisdiction-selection task. EC returns a mapping from asset descriptions to applicable statutory citations. EV returns the corresponding citation–amount claims. EC and EV share an underlying source case, although their natural-language fact renderings need not be identical. They are correlated task views, not two independent datasets.

**Data provenance.** Development cases are generated with the unmodified OpenExempt generator, pinned at commit `ec6fa2547431096588ce2d3ef107b8adc33cd4fe` [1]. The current mechanism run has 32 source cases, divided into four batches of eight, with both EC and EV tasks for each source. Generation settings specify two to four assets, a married-case ratio of 0.5, and state jurisdictions Arizona, Illinois, Oregon, Pennsylvania, and Wisconsin. Federal provisions can also appear in the public allowable framework. These 32 generated sources are development data, not the complete 9,765-sample benchmark or a formal held-out evaluation.

**Information boundary.** All four current control/treatment predictions for a batch are recorded before that batch's targets are released for grading and learning. The teacher can access released training targets, but neither actor nor teacher receives private symbolic construction fields as an inference tool. The benchmark solver is used for data construction and target generation, not as an actor tool. No separate validation set is used: seen-source replay is part of training optimization. Previously inspected sources remain development/training data and cannot later be relabelled as held-out test data.

**任务定义。** 律师执行器接收任务公开事实、法律和题目给定的前序解答。当前配置已给出可选豁免法域，不要求模型重新求解前序法域识别任务。EC输出资产描述到全部适用法条的映射；EV进一步输出法条与金额。EC和EV来自同一底层来源案件，但自然语言事实表述不必逐字相同，不能算成两个独立数据集。

**数据来源。** 开发数据使用未修改的OpenExempt生成器，固定版本为上述提交[1]。当前机制试跑包含32来源、四批、每批8来源，每来源各有EC和EV任务。生成设置为每案2至4项资产、已婚比例0.5，州范围覆盖亚利桑那、伊利诺伊、俄勒冈、宾夕法尼亚和威斯康星；给定框架中也可包含联邦豁免。当前32来源是开发数据，不是完整9,765题基准，也不是正式隔离测试。

**信息边界。** 每批四个对照或处理条件的预测全部保存后，才释放本批标签用于评分和学习。教师可以读取已释放训练答案，但律师和教师不能将私有符号字段作为推理工具。基准求解器只用于数据构建与生成标签，不是律师工具。不另设验证集，已见来源重放属于训练优化。被反复审查过的来源始终保留训练或开发身份，不能改名为隔离测试。

## 3. Current implemented method / 当前已部署方法

Implementation snapshot: `experiments/openexempt_online.py` and `legal_skill_guard/learning/task_scoped_skills.py`, source `492a7ee`; frozen configuration `configs/openexempt_direct_skills_online_20261020_run01.frozen.json`, contract `direct_statutory_claims` v13. These identify the deployed development implementation, not a frozen confirmatory study.

实现依据：上述源码及配置对应当前已部署开发实现，不表示正式确认性实验已冻结。旧算式运行保留为开发沿革，不与本运行拼接成绩。

### 3.1 Frozen actor and procedural skills / 冻结执行器与程序性技能

The actor is Qwen3-8B at model revision `b968826d9c46dd6066d109eabc6255188de91218`; its weights remain fixed throughout learning and inference. Skills contain EC/EV-specific procedural text and a public legal scope. Guidance is selected by the supplied task and allowable jurisdictions, rather than hidden target annotations or a learned answer router. A skill specifies factual conditions to inspect, the legal alternatives they enable, and exceptions that prevent unsupported claims. Numerical rules, when needed, are expressed in plain language.

The actor directly returns asset–citation sets for EC and citation–amount claims for EV. The same system instruction, public task, citation vocabulary, response schema, and generation budget apply to the empty-library control; the learned guidance is the intervention. Public labels are decoded through their declared citation mapping. No numerical interpreter, missing-claim insertion, asset-name repair, additional inference model, or answer-dependent retry is used. The current 4,096-token cap counts the complete serialized library, including metadata.

执行器为固定上述版本的Qwen3-8B，学习和推理中均不更新权重。技能包含EC/EV各自的程序性文本和公开法律范围，依据给定任务与可选法域投递，不依赖隐藏答案或学习得到的答案路由器。技能说明需要检查的事实条件、相应法律选项及排除不当主张的例外，必要的金额规则以自然语言表达。

执行器直接输出EC的资产法条集合及EV的法条金额主张。空库与带库共用系统指令、公开任务、法律词表、回答schema和生成预算，处理差别是学习得到的指导。公开标签仅按已声明映射解码，不使用数值解释器、不补漏主张、不修资产名称、不增加推理模型或按答案重试。当前4,096-token上限计算完整序列化库及元数据。

### 3.2 Teacher updates and publication / 教师更新与发布

After all first-encounter predictions in a batch are recorded, the teacher receives released training targets, actual responses, scores, and library state. The current teacher is `gpt-5.6-sol` with high reasoning effort. It proposes create, update, merge, or delete operations, with at most two candidate attempts per batch. The teacher is instructed to repair observed factual conditions, statutory alternatives, exceptions, or amount reasoning while preserving correct unrelated boundaries. Its communication packet includes every current source and a bounded selection of historical evidence; admission nevertheless replays all seen training sources.

For each task, public legal contexts define dependencies between edits: jurisdictions that occur together, moved skill identities, and changed shared guidance connect affected scopes. Connected components determine which edits are assessed together. Each accepted component needs current-source evidence and task-score preservation on current and prior sources, with strict current improvement; EV also preserves full-output F1. Accepted components form one library that must fit the total cap and pass the original whole-library gate. Composed requests must match already observed parent or proposal requests exactly; their raw responses are decoded afresh rather than selecting answers by case outcome. These checks constrain training averages, not every case or future-case performance.

本批全部首次预测完成后，教师获得已释放训练答案、实际回答、分数和当前库。当前教师为`gpt-5.6-sol`，high推理强度；每批至多两次候选尝试，支持创建、更新、合并和删除。教师按真实错误修正事实条件、法律选项、例外或金额推理，并保留正确的无关边界。通信覆盖全部本批来源及有界历史证据，准入仍重放全部已见训练来源。

每个任务分别从公开法律情境建立编辑依赖：共同出现的法域、技能标识的范围移动和共享指导改变连接受影响范围，由连通分量确定必须共同评估的编辑。通过分量须有本批来源证据，在本批及历史来源保持任务分数，并严格改善本批端点；EV还须保持完整输出F1。通过分量组成一个库，再检查完整容量和原整库门槛。组合请求必须精确匹配已观测父库或提案请求，原始回答重新解码，不按案件结果挑答案。检查约束训练均值，不保证每案或未来新案不下降。

### 3.3 Initialization, alternatives, and learning evidence / 初始化、替代方案与学习证据

The current run initializes an empty library once; subsequent batches use the actually published library. The fixed-initial condition is therefore the empty-library reference, not a static legal prior. The implementation also exposes task-level and whole-library submission policies for separately frozen ablations. Historical program-output experiments motivate the shared direct answer interface but are not spliced into its learning curve. Scope/replay mechanisms have prior art [3]; code-level checks or retrospective combinations cannot establish either novelty or subsequent-case benefit.

本运行仅在初始化时空库，后续各批使用实际发布的库。固定初始条件因此就是空库参照，不是静态法律先验。实现也保留整任务与整库提交策略，用于另行冻结的消融。历史程序输出实验为改用共享直接回答接口提供开发动机，不与新曲线拼接。作用域与重放已有相关工作[3]，代码检查或回顾性组合均不能证明原创性或后续新案收益。

## 4. Evaluation / 评价设计

**Endpoints.** EC and EV use the pinned original OpenExempt evaluator. EC measures citation-set agreement after its asset matching. EV additionally requires a citation–amount match under the upstream numerical tolerance. The implementation first obtains native per-case scores and then averages them separately by task. These are not the evidence-extraction F1 scores of the project's earlier ContractNLI experiments. The upstream scorer can ignore claims on unmatched extra predicted assets; a separately labelled full-output EV endpoint counts all predicted claims using the same claim-matching rule. It is calculated within case and then averaged across cases, rather than pooled across all cases.

**Controls and estimands.** The current development comparison is the evolving library versus the strong direct-answer empty library on the same first-encounter sources. The implementation retains three control names for audit continuity, but empty, fixed-initial, and direct-empty now produce identical requests; they are one reference condition rather than three independent baselines. Identical requests share a raw response and are not independent samples. B1 cannot establish online learning because the library is still empty. A knowledge-bearing static prior is a separate comparison that has not been run in this profile.

**Mechanism and cost.** Each batch should report source counts; first-encounter scores; paired gains and harms; proposed, rejected, and published edits; parent/child hashes; library size and tokens; guidance actually delivered; invalid responses; physical model calls; teacher attempts and tokens; and wall-clock time. Text delivery is not proof that a skill caused an improvement; controlled memory interventions and policy ablations remain necessary for attribution. More skills, more calls, or more successful training gates do not themselves demonstrate useful learning.

**Confirmatory work not yet frozen.** A formal evaluation still requires a predeclared source-disjoint train/test design and sample sizes, independently repeated learning runs, a faithful adaptive-memory baseline, cost-aware comparisons, and source-level uncertainty. The ACE runner is implemented in isolation but has not completed a real baseline run. The primary contrast, aggregation, CI/test procedure, multiplicity handling, and stopping rules for that formal experiment must be frozen before accessing its outcomes. The final test uses a frozen method and library; test results must not be used for further library selection.

**指标。** EC和EV采用固定版本的原OpenExempt评分器。EC按资产匹配后的法条集合计分；EV还要求法条与金额满足上游匹配及数值容差。先计算原单案分数，再分别按任务取均值。这不是项目早期ContractNLI的依据抽取F1。原评分器可能忽略无法匹配的额外预测资产，因此另列完整输出EV指标，按相同主张匹配规则计入全部预测；先在案内计算，再跨案平均，不将所有案件直接汇总成一个微平均。

**对照。** 当前开发比较是在同一批首次新案上，进化库相对强直接回答空库的差异。为审计续接保留的空库、固定初库与直接空库三个名称，现在产生相同请求，代表一个参照条件而非三个独立基线。相同请求共享原始回答，不是独立样本。B1技能库仍为空，不能证明在线学习。含法律知识的静态先验须另作比较，当前profile未运行。

**机制与成本。** 每批记录真实来源、首次表现、配对收益与损害、候选与拒绝及发布编辑、父子hash、库规模和token、实际投递的指导、非法回答、物理调用、教师消耗与墙钟时间。文本送达不证明技能造成改善，归因仍需受控记忆干预与策略消融。技能多、调用多、训练准入通过均不能单独证明有效学习。

**尚未冻结的正式实验。** 仍需事前确定来源隔离与样本量、独立学习重复、忠实经验基线、成本对照和来源级不确定性。ACE完整运行器已隔离实现，但未完成真实对比。正式实验的主比较、聚合、置信区间与检验、多重比较及停止规则须在查看结果前冻结。最终测试冻结方法和库，不能据测试结果继续选库。

## 5. Results / 结果

[PENDING RESULT — formal primary EC/EV and full-output EV table; method versus strong direct-empty, a separately specified static-memory control, and adaptive-memory baselines; estimates, 95% CIs, independent source n, completed/planned/invalid counts.]

[PENDING RESULT — batchwise first-encounter paired differences and cumulative differences; separate training replay; all learning repeats, publication events, and harmful-case frequencies.]

[PENDING ANALYSIS — scope-level versus task-level/whole-library admission, controlled guidance effects, actual delivery, legal-context transfer, and full compute costs.]

正式结果待填。当前B1/B2开发得分仅进入内部证据表，不填入正式主表，不从旧实验拼接曲线。

## 6. Discussion and scope / 讨论与边界

The present setup studies synthetic statutory-rule application in the exemption domain with supplied laws and allowable jurisdictions. It does not establish competence on Chinese law, open-world legal retrieval, real-client advice, or broad legal reasoning. Replay-based preservation is a training property and need not generalize to unseen cases. The final discussion must examine negative transfer, teacher supervision and cost, template dependence, benchmark-scoring limitations, and whether guidance changes legal selection rather than merely response presentation. [PENDING RESULT — conclusions warranted by the completed formal study.]

当前范围是给定法律与可选法域下、豁免领域的合成法律适用，不证明中国法、开放法律检索、真实咨询或广泛法律推理能力。重放保持是训练性质，不保证新案。最终讨论必须解释负迁移、教师监督与成本、模板依赖、评分局限，以及指导是否改变法律选择而非仅改变呈现方式。[待正式结果形成结论。]

## References / 已核实参考来源

1. Servantez, S., Lawsky, S. B., Jain, R., Linna Jr., D. W., and Hammond, K. (2026). *OpenExempt: A Diagnostic Benchmark for Legal Reasoning and a Framework for Creating Custom Benchmarks on Demand*. [Paper](https://arxiv.org/abs/2601.13183); [author repository](https://github.com/servantez/OpenExempt). Dataset, generator, evaluator, and symbolic targets are upstream contributions, not ours.
2. Zhang, Q., et al. (2025; revised 2026). *Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models*. [arXiv v3](https://arxiv.org/abs/2510.04618v3). Native generation/reflection/curation is a comparison target; no completed comparison is claimed here.
3. He, Y., and Yang, W. (2026). *SkillCommit: Evolving Agent Skills through Behaviorally Validated Scope Expansion*. [arXiv v2](https://arxiv.org/html/2608.15165v2). Closest-neighbour scope/replay contributions must be credited and distinguished before a novelty claim.

当前仅核实上述与本稿直接关联的来源，不声称已经完成相关工作综述；模型卡、完整基线与其余必要文献待逐项补齐。没有编造引用、统计显著性、理论保证或发布链接。
