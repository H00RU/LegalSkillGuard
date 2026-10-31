---
name: "paper-abstract-intro"
description: "逐句写或改 ML 论文的题目、摘要和引言：摘要 8 句、引言 6 段逐句模板（含词数、功能、范文原句、本文示例），领域级三挑战与三贡献对应，图 1/图 2 摆放，以及对齐稿与对应表的交付格式。写摘要、引言、题目时使用。"
---

# 摘要与引言：精确到每一句

骨架来自作者自己的范文 FlowSteer（NeurIPS 版源码 `FlowSteer-main_neurips.tex` 第 153–190 行）和 SkillFlow（arXiv 2605.14089），已在 EvoSteer、CollabFlow、R²Flow、R²Orch 上逐句落地。

## 0. 工作方式（每次都这样做）

1. **先拿范文源码**，把要写的部分拆成句，记下每句的功能和词数。
2. **先交对齐稿，不改文件**。
   - 开头放一张对应表，说明三个挑战和主线落在哪里：

| 挑战（摘要 S2 = 引言 P4 = 图 2 图注 = RQ，同名） | 对应创新 | 摘要 | 引言 P5 | 方法 | 命题（一句白话） |
|---|---|---|---|---|---|

   - 表下用一句话写主线出现在哪几处、每处一次。例如"两层 RSI 只在摘要 S3/S6、引言 P5-1/P5-2、图 1 图注、方法 4.1 开头各出现一次"。
   - 然后是逐句对照表：

| # | 范文原句（词数） | 本文英文（词数） | 本文中文 |
|---|---|---|---|

   - 每句词数和范文相差不超过 ±3。超出时说明原因。
   - 表后列出"需要你确认的点"：范式名、命名总数、哪些句子是等实验的占位。
   - 再附一份可直接粘贴的 LaTeX，含引用键；新增 bib 键单独列出。
3. **确认后才写入** `main.tex` 或 `sections/00-abstract.tex`、`01-introduction-related.tex`。同步中文版，本机重编。
4. **在 tex 里给每句写注释**，例如 `% S3 [31w] paradigm name + dash gloss`。注释里写清这句必须带的可辩护差异，以及禁区，例如 `Do NOT claim a reward-timing difference`。词数用脚本回填，不手数。
5. 引言改了，摘要同步改；摘要改了，引言 P4/P5 同步改。挑战名、贡献名在摘要、引言、图 2 图注和 RQ 里必须一字不差。
6. 改名后（例如 R-PlayFlow → PRFlow → R²Orch），题目、摘要、引言、图注、中文版一起换，再全局搜一遍旧名。

## 1. 题目

- 格式：`NAME: 一句直白的内容描述`。例如 "EvoSteer: Online Self-Evolving Graph Orchestration via Reference-Anchored Credit Assignment"。
- 题目要带出主线。例如 "R²Orch: Recursive Self-Improvement for Agent Orchestration via Self-Play within a Skill-Internalization Loop"，带出了两层 RSI、编排、自博弈和技能内化。
- 副标题直说做了什么，不放过细的技术名（Sub-Trajectory Balance、Balance 之类），也不放半术语。
- 方法名不和已有方法撞名。很多 "*Flow" 名字已被占用：AFlow、AgentFlow、FlowReasoner、ScoreFlow、EvoFlow 等。
- 给 3–5 个候选，每个注明含义和风险，由用户选。

## 2. 摘要：8 句（范文 FlowSteer 163 词，SkillFlow 约 211 词，同行常见 210–280 词）

| 句 | 词数 | 功能 | 模板 |
|---|---|---|---|
| S1 | 14–18 | 领域背景，一句 | In recent years, [X systems] have been widely applied to [goal]. |
| S2 | 28–42 | 三个挑战，用名词短语命名，顺序和引言 P4 一致 | However, existing [X] still faces key challenges, including *A* that …, *B* that …, and *C* that …. |
| S3 | 28–31 | 范式名 + 破折号（或冒号）释义，释义必须带出与范文的可辩护差异 | To address these challenges, we propose NAME, a new paradigm of [Paradigm]---[一句白话说清谁做什么]. |
| S4 | 23–30 | 支撑对象（环境、表示或训练目标），名称加缩写，"a … that …" | To support this paradigm, we introduce *[Object]* (ABBR), a [类别] that [作用]. |
| S5 | 35 | 机制，"in which …" 说清机制怎么运作 | Built on [S4 的对象], we further propose *[Mechanism]*, in which …. |
| S6 | 15–20 | 补充一个性质 | Moreover, [NAME/ABBR] …. |
| S7 | 14–22 | 结果，列任务族，不报具体数字 | Experimental results on [N] datasets show that NAME significantly outperforms baselines across [task families]. |
| S8 | 6 | 代码 | Our code is available at [匿名链接]. |

范文原句（FlowSteer）：

- S1 (14) In recent years, agentic workflows have been widely applied to solve complex human tasks.
- S2 (28) However, existing workflow construction still faces key challenges, including human-dependent workflow construction, the lack of graph-level execution feedback, and the inability to repair errors in-loop during long-horizon construction.
- S3 (28) To address these challenges, we propose FlowSteer, a new paradigm of Agent Designing Agentic Workflows — a single agent itself end-to-end designs the workflow that a downstream executor runs.
- S4 (23) To support this paradigm, we introduce the Workflow Canvas, a novel executable graph-state environment that returns syntax-checked execution feedback for every atomic edit.
- S5 (35) Built on the canvas, we further propose Reinforced Progressive Canvas Editing, in which a lightweight policy agent issues one atomic edit per turn conditioned on real canvas feedback, and is trained end-to-end via reinforcement learning.
- S6 (15) Moreover, FlowSteer provides a plug-and-play framework that supports diverse operator libraries and interchangeable LLM backends.
- S7 (14) Experimental results on twelve datasets show that FlowSteer significantly outperforms baselines across various tasks.

本文示例（EvoSteer 定稿，共 204 词）：

- S2 (42) However, existing self-evolving orchestration still faces key challenges, including *post-hoc evolution* that revises the team only after the trajectory ends, *credit diffusion* that gives every action the same terminal advantage under confounded baselines, and *skill admission* that is uncalibrated and never retired.
- S3 (31) To address these challenges, we propose EvoSteer, a new paradigm of Online Self-Evolving Graph Orchestration---the orchestrator builds a running team and repairs its plausible but failing steps from execution features and a learned value estimate.
- S4 (30) To support this paradigm, we introduce *Anchored Trajectory Balance* (AnchorTB), a regression-style flow-matching loss that assigns each orchestration action a coefficient by balancing subtrajectories against a frozen reference.

本文示例（R²Orch 定稿，共 193 词，ACL）：

- S2 (32) However, existing orchestration learning still faces key challenges, including *hand-designed curricula*, *advantage collapse* when a task's rollouts all reach the same outcome, and *unreliable evaluation signals* that judge each skill by one noisy score.
- S3 (37) To address these challenges, we propose R²Orch, a new paradigm of *Recursive Self-Play Orchestration*: an inner loop of self-play that improves the orchestrator on self-chosen tasks, and an outer loop that improves how the inner loop improves.
- S4 (28) To support this paradigm, we introduce *Recursive Learnability*, a training objective that rewards a Proposer for choosing tasks whose rollouts keep reaching different outcomes as skills are withdrawn.
- S5 (30) Built on this objective, we further propose *Skill Withdrawal*, in which the outer loop withdraws each skill once a controlled evaluation within self-play shows that the orchestrator performs as well without it.
- S6 (31) Moreover, the two loops form one cycle: failures are distilled into skills, skills into parameters, and withdrawals lead the Proposer to new failures, so the orchestrator moves toward zero-skill deployment.
- S3 比范围多 6 词，因为要同时写出内外两层循环，作者确认后保留。S6 写的是两条循环怎样闭合，以及闭合的结果。

摘要的规则：

- 不用否定句式。例如不写 "without X"、"not …"、"never …"；S2 的挑战用"做了什么"来描述。
- 不出现具体数字、超参数、"first"、"large-scale"。
- 三个挑战按结构对应：S2 的 A、B、C 分别对应 S3、S4、S5。S6 是附加性质，不对应挑战。
- S2 的三个挑战必须是领域里公认的宽泛问题，同行文献里已有人提出，能引到文献。不能是只有采用本文机制之后才出现的窄问题。R²Orch 初稿的 static curriculum、skill-anchored frontier、success-rate gates 因此被否，定稿换成上面三个。
- S3 破折号后的释义是整篇最难写的一句：要通俗，要带出差异，例如"运行中的团队"和"读执行特征与价值估计"。也可以用冒号引出，例如 R²Orch。
- S5 停在系统层面，不写操作细节。例如"对组内一部分 rollout 隐藏技能"留给方法节。
- S7 在实验结果出来之前不写 significantly；R²Orch 定稿用 consistently。
- 不把方法写成对比基线的组合，也不写基于某个基线。不用学术里不通用的词，例如 sibling。
- 摘要是一个段落：tex 里句与句之间只能有注释行，不能有空行，否则会断成几段。
- 交付给投稿系统时，另给一份去掉 LaTeX 命令的纯文本版本。

## 3. 引言：6 段（范文 FlowSteer 611 词，SkillFlow 811 词；超过 900 词就要压。R²Orch 在 ACL 8 页里是 531 词，不含引用）

### P1：一句，32–48 词

- **功能**：领域进入"多智能体或智能体系统解决复杂任务"的阶段，并点出演进方向。
- **模板**：In recent years, a variety of powerful [X systems] have been applied to solve a wide range of [tasks] \citep{3 篇奠基作}, gradually moving beyond [旧形态] toward [新形态].
- **范文** (32)：In recent years, a variety of powerful agentic systems have been applied to solve a wide range of human problems, gradually moving beyond single-turn question answering (QA) toward executable end-to-end task completion.

### P2：两句，约 70–90 词；图 1 用 wrapfigure 嵌在这一段

- **S1**（约 40 词）。功能：本文对象是"关键桥梁"，冒号后说它怎么带来好处。
  - 模板：In this process, [object] has become a key bridge from task goals to [reproducible execution]: by [怎么组织], [agents/systems] can complete complex tasks with improved [三个好处], as shown in Figure 1.
  - EvoSteer 示例：… by assigning each node a role and bound skills and each edge a communication protocol on an agent communication graph (Fig. 1, left), agents can complete complex tasks with improved controllability, compositionality, and reusability \citep{…}.
- **S2**（约 32–45 词）。功能：实践中的总问题，后果写成"代价高"或"无法做到"。
  - 模板：However, in practice, [object] still [现状] \citep{…}, making it costly to [迁移或检测] … and impossible to [本文要做的事].
  - 这一句就是全文主线的第一次出现。EvoSteer 写的是 "its outputs still look plausible, and impossible to repair while the workflow is still being executed"。
  - R²Orch (29)：However, in practice, orchestrators still learn from tasks people collect and lean on in-prompt skills \citep{…}, making them costly to scale and hard to improve on their own.
- **图 1**：放在本段，半栏 wrapfigure（约 0.68\textwidth）。图注第一句就是论点，例如 "Outputs that look plausible can still be headed for failure."

### P3：三条已有路线，4 句，约 70–150 词；图 2 放第 2 页顶部

- **S1**（17 词）：To address these issues, three main lines of work have emerged, as shown in Figure 2.
- **S2**：First, *[路线 A]* [做什么] \citep{2–3 篇}, [一个分词短语点出它的定位，如 treating the team as an object of learning].
- **S3**：Second, *[路线 B]* … \citep{…}, telling ….
- **S4**：Third, *[路线 C]* … \citep{…}.
- 三条路线对应图 2 的 (a)(b)(c)，本文是 (d)。路线名用同行常用说法，斜体。
- 三条路线的顺序和 P4 三个挑战的顺序一致。R²Orch：learned orchestration 对 (i)，self-improving agents 对 (ii)，skill scaffolds 对 (iii)。
- 这一段只描述，不批评，批评留给 P4。

### P4：三个挑战，约 155–222 词

- **引导句**：However, these methods still face three challenges. 可以在这里引用图 2 的失败标记，例如 "(Figure~2a--c)"。图 2 在讨论已有工作和挑战的地方引用。
- **每个挑战一个加粗名字** `\textbf{(i) Name.}`，名字和摘要 S2 一致。名字可以比摘要短，例如 "(iii) Uncalibrated skill admission."
- **每个挑战 1–2 句，固定三拍**：
  1. 现有方法具体怎么做，加引用。
  2. 为什么出问题，即机制层面的原因，加引用。
  3. 落到可观察的后果，"so …"。
- **EvoSteer 示例 (i)**：Self-evolving orchestration revises the team after the trajectory ends, by rounds or batches \citep{…}; during execution the orchestrator can only keep adding agents, and the decisive error is locally indistinguishable from a recoverable step \citep{…}, so a wrong agent is neither rerun nor removed until the task has failed.
- **R²Orch 示例 (ii)**（49 词，领域公认的问题加最近邻竞争者）：**(ii) Advantage collapse.** Group-based RL such as GRPO learns from differences among a task's rollouts, which vanish when they all reach the same outcome \citep{…}; self-play keeps tasks at the solver's frontier with skills in context \citep{…}, so withdrawing a skill pushes the tasks it supported toward all-wrong rollouts, and advantage collapse returns.
- **范文 (iii) 的收尾句式**，可以直接借：…, leading to sparse, delayed learning signals, shortcut behaviors (e.g., …), and unstable long-horizon credit assignment.
- **措辞禁区**：
  - 挑战一不写"人工指定"，写"预先定义"或"运行后才修改"。
  - 不用会被反问的词，例如"侵蚀准确率"。
  - 不贬低别人，只陈述机制。
  - 引用最近邻竞争者时，在同一句里点名，零字数成本。
  - 挑战要宽泛（见摘要规则），不能只在本文机制下才成立。

### P5：贡献，约 137–218 词，散文，不用 bullet

句序固定，和摘要 S3–S6 一一对应：

1. To address these challenges, we propose **NAME** (Fig. 2d), a new paradigm of *[Paradigm]*, in which [S3 释义展开]---replacing the [旧循环] loop.
2. 一句说范式怎么运作的关键细节，对应挑战 (i)。例如 "The orchestrator issues one atomic edit per turn, rerun and drop included; each is executed at once, …"
3. To support this paradigm, we introduce *[Object]* (ABBR), …（与摘要 S4 几乎同句）。对应挑战 (ii)。
4. It combines … / 一句说对象的关键性质（与摘要 S6 对应）。
5. Built on …, we further propose *[Mechanism]*: [分号串起机制的三四个步骤]。对应挑战 (iii)。
6. 收束句：Trained end-to-end on …, NAME turns [A], [B], and [C] into one set of learned decisions under a single training objective.

- 可以先用一句给后文的标签做铺垫。R²Orch 的 P5-2（15 词）："Two channels join the loops, one carrying the objective down and one the evidence up."，后面两句分别称为 the downward channel 和 the upward channel。
- R²Orch 的收束句（37 词，对应摘要 S6）："The two loops thus close into one cycle: failures are distilled into skills, skills into parameters, and withdrawals lead the Proposer to new failures, so the Director improves on its own and moves toward zero-skill deployment."

规则：

- 贡献不能写成工程描述。例如"通信边汇聚证据、写权限保证可串行化""同一框架支持三类团队"这类句子要删掉。
- 自创名字不超过 3–4 个。描述性短语用小写，不算命名。
- 贡献句不写"基于 X""结合 X 与 Y"，P5 里不致谢对比基线。对比只放在 P3、P4 和相关工作里。

### P6：实验与意义，2–4 句，约 69–93 词

- **S1**：We evaluate on benchmarks across [任务族列表].
- **S2**：Results show NAME outperforms [基线族，按类型列] on every benchmark and improves all [N] executors---a foundation for [一句愿景].
- **可选**（范文有）：
  - As shown in Figure 2, … effectively bridging the gap between [旧] and [新]。R²Orch 把图 2 的引用放在 P4，这句就不用。
  - This work lays a foundation for building the next generation of ….
- R²Orch 示例：
  - "Results show that R²Orch outperforms all baselines on every benchmark, improves six other Worker backbones without retraining, and keeps its accuracy when tested with zero skills."（25 词，三个结果各对应一张图表）
  - "Together, these results mark a step toward the recursive self-improvement of agent orchestrators."（13 词，呼应题目）
- 页数紧张时只保留 S1、S2，把愿景并进 S2 的破折号之后。

## 4. 页面与浮动体

- 引言开头放 `\suppressfloats[t]`，避免图 1 跑到标题上方。
- 图 1 是 wrapfigure，嵌在 P2；图 2 是全栏 `[t]`，落在第 2 页顶部。
- 引言必须在第 2 页结束。超了就逐句压缩，优先压 P4、P5，不缩图。
- 改完确认第 2 页的结尾不变，段尾行写满（见 paper-layout-submission）。

## 5. 自检清单（交付前逐条过）

- [ ] 摘要 8 句，每句词数都已标注，总词数和范文的差距已记录。
- [ ] 摘要没有否定句式，没有数字，没有 "first"；实验未定时没有 significantly。
- [ ] 摘要是一个段落，句间没有空行。
- [ ] 三个挑战是领域级的宽泛问题，每个都有文献支撑。
- [ ] 三个挑战名在摘要 S2、引言 P4、图 2 图注和 RQ 里一致。
- [ ] P5 的每句都能对上一个挑战。
- [ ] 主线在摘要 S3/S6、P5、图 1 图注各出现一次，没有反复重申。
- [ ] 摘要和引言没有把方法写成对比基线的组合，也没有写基于某个基线。
- [ ] 动词对得上代码，例如 Proposer chooses，不写 generates。
- [ ] 每条引用都核实存在，近期工作占多数。
- [ ] 术语和同行一致，首次出现时已消歧（例如 anchor、online、reference 在同行里另有含义）。
- [ ] 中文版同步，不用破折号。