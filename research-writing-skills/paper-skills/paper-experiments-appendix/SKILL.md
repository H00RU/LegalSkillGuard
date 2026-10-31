---
name: "paper-experiments-appendix"
description: "逐段写或改 ML 论文的实验节、结论和附录：RQ 设计、实验设置、结果段\"结论→原因→证据\"写法（讲清为什么赢）、消融与机制分析、对照实验清单、两句结论，以及附录的理论证明、实验细节、案例研究与措辞中立。写实验、结论、附录时使用。"
---

# 实验、结论与附录：精确到每一段

图表画法和数据核查见 paper-figures-data 技能，这里只管文字和结构。

## 1. 实验节结构

```
\section{Experiments}
  RQ 列表（一段）
  \subsection{Experimental Setup}          Datasets / Baselines /（Metrics）/ 实现一句
  \subsection{Main Results and Backbone Transfer (RQ1--RQ3)}
  \subsection{Component Analysis (RQ4, RQ5)}   按方法 4.1/4.2/4.3 各一个加粗段
```

页数紧张时，用 `\noindent\textbf{}` 加粗段首代替 5.x 小节，RQ 编号写在小节标题里。

## 2. RQ 列表：一段，5 个问题

- **开头句**：We evaluate NAME through the following research questions (RQs).
- **每个 RQ 一个问句，用加粗编号**：

| RQ | 问什么 | 对应证据 |
|---|---|---|
| RQ1 | How does NAME compare with the baselines in distribution? | 主表 IID |
| RQ2 | Does it generalize to held-out benchmarks? | 主表 OOD |
| RQ3 | Does it transfer across executor backbones? | 迁移图 |
| RQ4 | What does each component contribute, and how do fixed paradigms compare? | 消融表 |
| RQ5 | How does [目标] compare with other objectives, and do [机制] behave as designed? | 目标对比图、机制图 |

- **R²Orch 体例**（每个创新点一个 RQ）：RQ1 是分布内和留出基准的主结果，RQ2 是跨 Worker 骨干迁移，RQ3、RQ4、RQ5 各对应方法节 4.1、4.2、4.3 的一个创新点，问句末尾带节号。
- RQ 围绕正文的三个创新点设计，可以改写 RQ 来服务创新点。
- 指标要直观（准确率、计数、曲线、AUC），不用秩相关、采样比例这类要解释半天的指标。

## 3. 实验设置：三段，各 2–4 句

页数紧时压成一个 `Setup.` 段两句：数据集与划分一句，基线家族加共享协议一句，细节全放附录 D。

### Datasets.

1. **IID 句**：Six in-distribution (IID) benchmarks supply the training tasks and IID tests: A \citep{}, B \citep{}, ….
2. **OOD 句**：Six out-of-distribution (OOD) benchmarks are held out: ….
3. **规模与划分**：Each test set has 128 items (AIME 2026: 30) disjoint from training.
   - 划分的细节放附录。可以只写"划分在代码中公开"。

### Baselines.

1. **按家族列**：We compare with direct prompting (…), backbone training (SFT, GRPO \citep{}), workflow search (…), RL-trained orchestration (…), and skill evolution (…).
   - 数清家族数，结果段引用时保持一致（R²Orch 是六类，直接提示也算一类）。
2. **公平性**：All use [同一执行器] as executor and trained model, the same training tasks, and their authors' best configurations.
3. **例外情况**：例如哪个更大的模型只用来写候选技能。
4. **测试协议**：NAME is tested with learned parts frozen, and every test score is a five-run mean (Appendix~D).

### Metrics

- 篇幅允许时单列一段；否则把 "Ans EM/F1, Acc., Pass@1, SR, resolved rate" 的定义放附录 D。

## 4. 结果段：每段"结论 → 原因 → 证据"

### 核心要求：讲清为什么赢

- 用户最在意的是每段解释"为什么"。只复述表里的现象（超过了谁、高了多少）的段落会被整段退回。
- 原因要落到正文的创新点上。证据优先用消融表里代价最大的那些列，数字只留能支撑原因的，不堆主表数字。

### 主结果段

- **R²Orch 定稿写法**（对比全部方法家族，用于 8 页的 ACL）：
  - **S1 结论**：NAME is best on all twelve benchmarks against six families of baselines, and its lead holds on the held-out half at zero skills (Table 1).
  - **S2 排除替代解释**：Training the backbone alone changes little, while orchestration lifts the frozen Workers far higher, so the gains come from how the Workers are organized.
  - **S3 各家族为什么不行，按引言的挑战归类**：The other orchestrators learn from signals that stop tracking the Director: fixed task pools (workflow search, RL-trained orchestration), success rates or budgets (skill internalization), and frontiers measured with skills in context (self-play).
  - **S4 本文用什么取代这些信号，领先最大的列正是消融代价最大的列**：NAME replaces these signals with [创新点 A] and [创新点 B], so its lead is largest on AIME 2026, WebShop, and ALFWorld, where the ablations cost most (Table 2).
  - **禁区**：不点名最强基线并写"本文是它们的结合""它们各跑了本文的一个循环"，这等于承认方法基于它们；也不逐个基线比较。
- **FlowSteer 的写法**：As illustrated in Table 1, NAME achieves consistent improvements … We attribute these gains to three interlocking design choices. First, … Second, … Third, …。每个 First/Second/Third 对应一个创新点，并点出它带来最大收益的任务类型。
- **EvoSteer 的写法**（更紧凑，用于正文 9 页限制）：
  - **S1 结论加关键差距**：EvoSteer is best on all twelve benchmarks (Table 1), ahead of the strongest baseline by 2.81 EM and 4.01 accuracy points on IID averages and by 3.36 and 2.53 on OOD, with standard deviations at most 1.83.
  - **S2 最大和最小收益加原因**：The lead is largest on AIME 2026 (8.67) and smallest on MATH-Hard (0.78), where the backbone is near its ceiling.
  - **S3 归因，排除替代解释**：Training the backbone alone (SFT, GRPO) adds at most 6.09 points …, so the gain comes from orchestration over the same frozen executor.
  - **S4 额外对比**：with a 9B executor EvoSteer beats the larger DeepSeek-V4-Flash on every benchmark.

### 迁移段

- 写法：The trained orchestrator transfers unchanged to six other executors and improves all 72 backbone--benchmark scores (Figure 4a,c), so one trained policy serves every executor.
- 补一句为什么能迁移，例如 "since the roles and hand-offs it builds fit any Worker"。
- 然后写规律和原因，例如 "Weaker backbones gain the most, narrowing the IID range across backbones from 25.7 to 6.4 points, because the graph supplies the planning and checking they lack"。

### 组件分析：按方法小节各一个加粗段

- 段首标题写成 "Online orchestration (Section~4.1)." 或 "Recursive Learnability (RQ4)."，读者能直接对回方法。
- 每段的句序：
  1. 一句总结论，加表格引用；
  2. 机制层面的原因，例如 "Since most of each group hides the candidate skill (Eq. 4), updates teach the Director to succeed without it, and zero-skill accuracy overtakes the accuracy with skills midway (Figure 4a)"；
  3. 一个对照实验说明"为什么是这个机制起作用"，例如保留其他、只去掉 $f$，或只把目标换成在当前上下文上测；
  4. 机制按设计工作的直接证据，优先取日志，例如 "All 12 withdrawals pass Eq. (14) on the card's own contrasts, with posterior E[Δ⁺] at most 0.019"（见 paper-figures-data 的 E.12）。
- 替代方案落后的原因必须对每个替代方案都成立。"成功率混入了课程"只能解释成功率阈值为什么差，不能顺带解释预设预算和验证差值；后两者只写"同样落后"。
- 目标对比的写法："With only the loss changed, [目标] beats [A, B, C, D] by 3.17--8.81 IID points"，再补一句计算成本处在同一量级。
- 最后一段 "Architecture and training."：拆开架构本身和训练各贡献多少。

### 落稿前逐词核对

用户常说"仔细核对后再改"。逐句对照表、图、方法节和日志，再落稿：

- 数量词和 Setup 一致（几类基线、几次撤出）。
- 绝对词要成立。例如"只有混合组才有 GRPO 信号"不成立，因为奖励里还有成本项，结果一致的组也有很小的优势；改成"混合结果，因而有非零的 GRPO 信号"。
- 强结论不超过证据。日志显示被撤的多是试用卡、不少后来被恢复时，不写"内化后才撤出"，写"不再帮助当前模型时撤出"。
- 主语不能偷换："the gains come from how the Director organizes them"会让人以为所有方法的收益都来自本文的 Director，改成"how the Workers are organized"。
- 代词指代唯一，同一句里两个 it 不能指不同对象。
- 核对中发现并修掉的问题，在回复里逐条说明。

### 篇幅

- 重写结果段时，总词数和原文持平（R²Orch：517 词改写为 509 词）。编译后确认正文末页仍在限制内，段尾行写满（见 paper-layout-submission）。

### 写作规则

- 每段先给结论，再解释为什么成立，并点回对应的创新点。不堆数字，只挑能支撑结论的。
- 不给单个格子硬套机制解释，不把预期的排序当成硬约束。
- 所有数字和表、图、附录、中文版完全一致。Avg 和 Δ 按 paper-figures-data 的 C 节重新计算。

## 5. 审稿人默认要的对照（按创新点准备）

- **在线修复类**：
  - 匹配调用预算的无引导重跑（Unguided Full Rerun）、随机节点干预、最后节点干预；
  - 报修复率、尝试预算、Repairs/1K calls，以及修复把原本成功的运行搞坏的次数。
- **信用与目标类**：
  - 广播加组归一化（GRPO）、PPO、TB、tempered TB 等，只换损失，其余不变；
  - 去锚消融三种：题间打乱、全局常数、噪声。
- **准入或门控类**：
  - 贪心接受（keep if score went up）、固定次数阈值、全部接受、只用固定次数的检验；
  - 报 false-commit 和 harmful-commit。
- **选题或课程类**：均匀采样、动态采样（DAPO）、选择性 rollout（GRESO）、在当前上下文上测的可学习性、解题率奖励、不确定性奖励，只换选题目标；报每轮额外 rollout、每个有效组的 rollout 和 token、GPU 小时。
- **撤出或退役类**：成功率阈值、预设预算、验证差值、固定脚手架，只换撤出规则。
- **固定范式对比**：用同一套架构跑几种固定编排范式。
- **成本**：训练和推理的计算量要和同行在同一量级。
  - 附录给出总 GPU 小时和总 token 数，例如 "95.98 H800 GPU hours and 1,580,691,323 tokens"。
  - 只报能互相推回的总量，推不回的平均值不报。
- 重训太贵时，消融尽量找推理期的替代做法：评测时干预、用已存的 checkpoint、离线分析日志。

## 6. 结论：2 句，约 40 词（FlowSteer 37 词，SkillFlow 41 词）

- **S1** 用冒号串起三个创新点：NAME unifies [A], [B], and [C] in one learned loop: each action …, [目标] credits it against …, and [机制] decide which ….
- **S2** 结果：It beats all baselines on [N] benchmarks and improves every executor backbone.
- 不写限制、不写未来工作，不用不带数字的 "reliable"。
- 结论和各 RQ 的口径一致。RQ 的措辞因证据收窄后，结论里的同一说法也要改，例如 "retires internalized skills" 改为 "retires skills that stop helping"。只在确认确实有问题时才改。

## 7. 附录结构

```
A  理论主体（以核心目标命名，如 Anchored Trajectory Balance）
   A.1 Formal Setting, Histories, and Legal Actions
   A.2 … 逐步推进的定义、引理、命题
B  估计量与实现细节（如 Shrinkage Baselines, Structural Pooling, and the Value Head）
C  检验与训练循环（如 Sequential Validation and the Training Loop）
   C.x Training Algorithm and Data Routing
   C.y Proofs of the Main-Text Propositions
D  Experimental Details
E  Case Study
```

### 措辞中立（硬规则，正文和附录都适用）

- 不写方法基于某个对比基线：不写"用 X 的编辑器""代替 X 的门控"，也不列某个基线特有的操作名（例如 expand、revise、compress、prune）。实现细节用中性描述，例如 "An LLM editor revises skills, the least helpful first, and distills new ones from groups in which both parts fail"。
- 借来的实现不点名，也不算作贡献。基线只出现在对比里：基线表、消融变体名、相关工作、参考文献。
- 图中的标签同样处理；tex 注释里的这类内容，上传源码前清掉。
- 改完在 PDF 文本里搜一遍基线名，确认剩下的都是对比用法。

### 术语和代码一致

- 同一个词在代码和论文里只指一件事。代码把正式撤出记为 retire，结论里的 retire 也指它；试用期满仍未收入的技能就叫 discarded（中文"淘汰"），不能也叫 withdraw。

### 理论附录写法

- **开头一段路线图**：This appendix treats three objects in turn: … We first establish …, then analyze … Algebraic identities hold on every recorded trajectory, and each distributional or statistical result holds under the assumptions it states.
- **每个结果都用带名字的环境**：`\begin{definition}[Context and complete-history representation]`、`\begin{lemma}[Strict growth and unique parentage]`。每个都有 `\label`，供正文命题引用。
- **每个结果先写它依赖的假设**，再写结论，然后证明。
- **正文命题的证明集中在一个小节**（Proofs of the Main-Text Propositions）。正文的证明指针写出依据的引理，例如 "Proof. Appendix A, via Lemmas A.5 and A.6, following \citet{…}"。需要补行时，这也是不加新主张的填充办法。
- **记号约定写在文件头注释里**，例如 "Actions use $a_t:s_t\to s_{t+1}$, $t=0,\dots,T-1$, throughout"。正文已有的公式只引用，不重新定义。
- 不用"任务难度"这类无法测量的名字，写实际的量，例如 "so changing $\rho_t$ alters measured success"。
- 附录一般不放文献引用。

### 实验细节（附录 D）：用 `\paragraph{}` 分块

1. **Benchmarks and splits**：训练集和测试集不相交；网格说明，例如 "one run's 0/1 metric lies on a $k/128$ grid … five-run mean on a $k/640$ grid"；子集怎么取。
2. **Metrics**：每个指标的精确定义和官方评测器。
3. **Baselines and fairness**：同一执行器、同一训练任务、作者最佳配置；同名基线在不同表里的区别（例如 GRPO$^\dagger$ 和 GRPO）。
4. **Ablation variants and fixed paradigms**：每个变体去掉什么、保留什么。
   - 控制变量的说法要和图中数字一致：各变体总 rollout 不同时，不写 "the rollout budget fixed"，写实际固定的量，例如 "the training rollouts fixed"。
5. **Hyperparameters**：一张配置表。正文里用符号表示的常数，数值都在这里；写出各角色的基座模型（例如 Director、Proposer、Worker 都是 Qwen3.5-9B）。
6. **Compute**：总 GPU 小时、总 token 数、步数，写明是训练实测还是外推（例如 "about 106 A100 hours measured in training"）。过时的来源说明（例如早期的局部重跑）要删掉。
7. **Repeated runs**：Every test score is the mean over five independent runs. 定义没把握时只写 five runs，不编造是独立训练还是重复评测。

其他措辞：

- **图注写清统计口径**：例如 "as a moving average over 10 cycles (dots: single cycles)"，不写含糊的 "over the last 10 cycles"。
- **留出口径**：OOD 基准和训练属于同一批领域时，写 held-out 或 OOD benchmarks，不写 held-out domains。

### 案例研究（附录 E）

- 只选一个最能体现全文主线的案例，例如"表面全对，但价值估计骤降，重跑后修正"。
- 案例必须没有数据泄漏，例如不能是训练用过的题。不确定就问用户，用户说删就删。
- 结构：
  1. 标题，例如 "Code That Passes the Visible Test"；
  2. 逐轮的轨迹框；
  3. 一段 `\noindent\textbf{Key Observations:}`，按时间顺序写：表面信号是什么、实际错在哪、价值估计怎么变（给具体数值）、编排器做了什么、结果如何。