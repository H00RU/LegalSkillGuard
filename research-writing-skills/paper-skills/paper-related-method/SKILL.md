---
name: "paper-related-method"
description: "逐段写或改 ML 论文的相关工作、预备知识和方法节：同行写法调研与术语碰撞、相关工作两段式、Definition/Problem Statement 写法、方法小节的\"目的句→公式→where 释义→命题\"节律、公式从权威结果出发与排版宽度、措辞中立（不写基于对比基线），以及公式推导的逻辑链和符号检查。写相关工作、预备知识、方法、公式时使用。"
---

# 相关工作、预备知识与方法：精确到每一段、每个公式

## 0. 先做同行写法调研（写相关工作和方法之前）

1. 拉 10–15 篇同行全文：近 1–2 个月的 arXiv，加最近邻竞争者和范文。存到工程的 `peer-papers/`。
2. 每篇按同一模板抽取：
   - 摘要每句的功能和词数；
   - 引言结构；
   - 术语表（同一概念别人叫什么）；
   - 方法节写法；
   - 实验惯例（基线、指标、对照组）；
   - 问题到方案的映射；
   - 与本文的碰撞点。
3. 产出一份 `同行写法研究-vN.md`，包含：
   - **术语碰撞表**：同行已经用某个词表示别的意思。例如 anchor 在 GiGPO/GACA 里指共享环境状态；online/test-time 有四种时间尺度；π_ref 在同行里只用作 KL 锚；admission 在同行里叫 commit/prune。每条都给出首次出现时的消歧写法。
   - **每个贡献的最近邻**，以及必须写出来的差异，精确到"它整轮跑完再改，我们每步之后就能改"这种程度。
   - **审稿人默认会要的对照实验**（交给实验节）。
   - **可直接借用的同行句式**（标出处，只借句式，不抄内容）。
4. 每条建议标等级：★ 必改、☆ 建议、○ 可选。只提建议不改稿，等用户批准。

## 1. 相关工作：固定两段，正文约 270–370 词

- 每段的段首是加粗主题名，例如 `\paragraph{Agent Task Orchestration.}` 和 `\paragraph{Skill Self-Evolution.}`，对应本文的两条主线。R²Orch 用的是 `Learned Orchestration and Self-Play.` 和 `Skill Evolution and Self-Improvement.`。
- **每段 3–4 句，句序固定**：
  1. **奠基做法**：[Objects] are searched/built under … \citep{2 篇}。
  2. **按动词分组列近期工作**：Later work evolves the team between runs \citep{}, mutates topology between test-time rounds \citep{}, repairs finished trajectories \citep{}, or audits unfolding prefixes \citep{}, but [这些做法共同的局限，用中性的事实描述，例如 keeps the running team fixed]。每组 1–3 篇，以 2026 年的工作为主。
  3. **（可选）第二个维度的分组**：Credit comes from A \citep{}, B \citep{}, or C \citep{} and its extensions \citep{}。
  4. **一句差异句**：NAME [做了什么不同]。正面陈述，不说 "first"，不贬低他人。
- 例句（EvoSteer 段末）：EvoSteer reruns and drops agents in the running team and measures flows from a frozen reference.
- 例句（R²Orch 段末）：R²Orch nests self-play in a skill-withdrawal loop and decides each withdrawal from the controlled evaluation within every randomized rollout group, at no extra rollouts.
- 圈出空白时用事实陈述，例如 "existing LLM flow objectives are stated on prefix trees or leave the non-tree case unexamined"。
- **按类别合并、分组引用，不逐篇讨论**。分组可以和实验的消融变体一一对应。例如 R²Orch 写技能 "are withdrawn on a success-rate threshold \citep{}, a preset budget \citep{}, or leave-one-skill-out validation \citep{}"，三组正好是三个撤出类消融。
- 对比基线在这里只按类别中性描述。差异句写本文做了什么，不写"在 X 之上"或"改进了 X"。
- **压缩**：页数紧时正文可以压到约 180 词（含引用约 290 词），R²Orch 定稿 183 词。靠合并分组省字，引用键全部保留。需要省版面时先压相关工作，不压预备知识。
- 相关工作必须留在正文，不能挪进附录，也不能另起第三段。

## 2. 预备知识：三块

- 文件头注释列出保留的记号，例如 x 任务、g 智能体图、r 验证器、π_θ 策略；方法节沿用，不重新定义。
- 工程对象（例如算子画布）放附录。正文只要对象、轨迹和部署目标。

### Definition 1：对象（约 66 词，一般不放公式）

- **模板**：`\noindent\textbf{Definition 1: [Object].}` A [object] is a directed (acyclic) graph $G=(V,E,\cdot)$, where [每个元素是什么，按出现顺序], and [输出如何确定].
- **借用前人定义时**，在句末括号里交代：(our typed edges and nodes extend the untyped topologies of \citet{…} and the computational graphs of \citet{…})。
- **对象名**用领域通用说法，例如 communication graph，不用自造的 team graph。

### Definition 2：轨迹（约 64 词加一个公式）

- **模板**：A complete sequence of $T$ [actions] from [初态] to [终止] defines a [trajectory], in which [关键约束，例如每个动作一发出就执行]:
- **公式**：一行写出 τ 的构成，用 ⇒ 指向结果或奖励；可以并列写出状态更新式。
- **where 释义**：按出现顺序解释每个符号。动作类型用 `\textsc{}` 全部列出。
- **最后一两句**：给出结构性事实，例如 "every non-root state has a unique parent"。说明哪些细节在后文展开（"made explicit in Eq.~(…)"）。
- 动作和算子很多时，附一张表（FlowSteer 的 Table 1：类别 / 算子 / 输出 / 类型 / 动作 / 图更新）。

### Problem Statement（约 88–123 词加一个公式）

- **模板**：Given a task $q$, [冻结的执行器、工具、参考策略、技能库], we seek [policy] $\pi_\theta$ trained toward [目标] \citep{…}:
- **公式**：目标分布或目标函数。
- **where 释义**：
  - 每个符号的含义和取值范围；
  - 每一项的作用，例如 "$R_\beta$ keeps a positive mass for failures while weighting a full score $e^\beta$ times a zero score"。
- **收尾句**：把公式和后文命题接上，例如 "Equation (2) is the training target; … lets action choices alone realize it."。R²Orch 的写法："Equation (2) is the deployed target; Section 4 shows how a shrinking scaffold and a learned curriculum approach it."
- 参考策略在这里第一次出现时，就说明它的角色。例如它只通过比值和实测统计量进入目标，没有 KL 项，因为同行默认把参考策略读成 KL 锚。

## 3. 方法节的段落节律（14 篇同行里 13 篇是这个节律）

### 节首

- **图 3**：全栏，`[t]`，放在方法节首页的顶部。图注按区域说明：Top/Bottom left/Bottom right 各一句。
- **路线图句**：As illustrated in Figure 3, this section introduces the NAME framework, including [A] (Section 4.1), [B] (Section 4.2), and [C] (Section 4.3), all built on [共同基础].

### 每个小节 4.x

1. **开场段，1–2 句**。先说目的，再说机制。说明对应图 3 的哪个区域，交代沿用的范式并引用。沿用的是通用范式（例如 Orchestrator–Executor），不是某个对比基线的方法。
   - 例：As shown in Figure 3 (top), EvoSteer follows an Orchestrator--Executor paradigm \citep{…}: a trainable orchestrator organizes tool-using agents, each on a frozen executor, inside a structured environment.
2. **3–5 个加粗 run-in 块**，用 `\noindent\textbf{Name.}`，不用 `\subsubsection`。每块的写法：
   - **承接**：先说为什么需要这一步，接住上一块留下的问题（R²Orch 的写法）。
   - **引导句**（以冒号结尾）：说这一步要得到什么。例如 "Each orchestrator action is validated, applied to the graph, and executed at once; its feedback and a fixed-length execution feature vector are appended to the state:"
   - **编号公式**：一个 `equation`，内含 1–3 个并列式，用 `\qquad` 隔开，加 `\label`。
   - **where 释义句**：按出现顺序定义每个新符号，13–23 词一句，可以写两三句。起头词可以换着用（Here / with / where），不要每块都是 where。
   - **一句"这带来什么"**：例如 "These features need no extra model call and cover the execution-side failure modes catalogued for multi-agent systems \citep{…}." 这句要能接到下一块。
3. **命题，放在小节最后**。写法：

```latex
\noindent\textbf{Proposition 1.} \emph{[一句白话，无数学符号，说本小节保证了什么]}
\emph{Proof.} Appendix~\ref{…}, via Lemmas~\ref{…} and~\ref{…}, following \citet{…}.
```

   - 每个小节恰好一个命题，命题下面不再放任何内容。
   - 不在命题后加边界句或限定句，例如 "This characterizes … not …"。用户已否决这种防御写法。
   - 命题的说法正好是附录证明的内容。被指出超出证明时，换成能严格证明的正面陈述，不改成"若……则……，不保证……"。
   - 证明指针写出依据的引理，必要时加上理论来源。例如 R²Orch 命题 1："Appendix~\ref{app:proofs}, via Lemmas~\ref{lem:decomp} and~\ref{lem:twotime}, following the two-time-scale analysis of \citet{borkar1997stochastic}"。需要补一行时，这也是不加新主张的填充办法。

### 措辞中立（硬规则，用户定为非常严重）

- 方法节不点名、不致谢对比基线。不写"用 X 的编辑器""代替 X 的门控""沿用 X 的触发规则"，也不用某个基线特有的操作名（例如 EXPAND、REVISE、COMPRESS、PRUNE）。
- 借来的实现细节用中性描述放附录 B–C。例如 "An LLM editor revises skills, the least helpful first, and distills new ones from groups in which both parts fail"。
- 对比基线只出现在引言、相关工作和实验里。方法 tex 的文件头注明这一点，例如 "SESA and PATS are background (introduction, related work, experiments) and are not credited here"。
- 可以写出处的是理论基础和通用算法，例如两时间尺度随机逼近、RLOO、GRPO、REPS、潜在结果框架、贝叶斯自助法、Thompson 采样，用 Motivated by 或 following 交代（见 4.3）。对象的定义借自前人时，照第 2 节在括号里交代。不能写的是把本文的机制或训练循环归到对比基线名下。
- tex 注释里的旧说法也要清掉，例如 "X credit stays in Section 4.2"，因为源码可能被上传。
- 改完在 PDF 文本里搜一遍基线名，剩下的只能是对比用法。

### 句子层面

- 平均句长 15–20 词。
- 借用的条件放在括号形容词里，例如 "(fixed-look)"、"(exact under the sign model)"，不写防御性的对比句。
- 附录指针写在括号里，例如 "(Appendix~B)"，不单独成句。
- 实现常数和超参数不进正文。正文只用符号，数值放附录 D 的配置表；方法 tex 文件头列出这些符号。
- 讲机制时可以用一个小例子带一遍，例如"researcher → generalist，ONE_WAY，仲裁命中哪条"。
- 动词和代码一致：代码里 Proposer 从候选列表里选题，就写 chooses，不写 generates。内部代号不进正文。

## 4. 公式推导的逻辑链（最重要）

### 4.1 整节是一条链，每个公式都被后面用到

典型顺序：

1. 状态与动作（Def. 2 → 状态更新式）
2. 策略与对数比（动作的 log-prob、相对参考的 log-ratio）
3. 残差与损失（子轨迹残差 δ，平方回归）
4. 估计量（锚、校正项、可学习残差）
5. 检验与预算（配对计数、p 值、α 分配）

后一个公式用 `Eq.~\eqref{}` 显式引用前一个。没有被后文用到的公式就删掉。

小节之间也是一条链，每个小节接住上一节交出的一项。R²Orch：4.1 把零技能目标拆成内层增益 Γ_t 和外层代价 C_t；4.2 提高 Γ_t（向下的通道）；4.3 约束 C_t（向上的通道）并闭合循环。

### 4.2 替换可学习量为实测量时，走四步论证梯子

同行 GFlowRL、RTMC、GACA 的固定顺序：

1. **结构性理由**：为什么这个量难学（时间尺度不匹配、稀疏二值奖励等）。
2. **"批里本来就有"**：这个量 rollout 已经记录了。
3. **不动点或闭式解**：引一个恒等式或附录命题。
   - 例：二值奖励下，TB 最优点的配分函数 $Z=1+(e^\beta-1)p_\rho(q)$，所以锚 $u_q=\log[1+(e^\beta-1)\hat p_q]$ 正是 $\log Z$ 的插入估计。
4. **只学剩余部分**：写明哪些量不带梯度，例如 "The measured terms are held fixed, so only $\pi_\theta$ and $b_\psi$ are updated."

### 4.3 每个公式从权威结果出发（含借用已有目标）

- 每个公式都从一个权威理论结果出发，再写本文改了什么，读起来有理论依据（SkillFlow TTB 体例）。
- 在方法 tex 的文件头列出每个公式的出处。R²Orch 的例子：
  - 两时间尺度随机逼近（Borkar 1997）→ 嵌套的近端最优响应和外层算子；
  - RLOO 加 GRPO → 随机上下文目标的无偏梯度；
  - REPS 加"KL 正则 RL 即推断" → 倾斜与累积量展开；可学习性 → Recursive Learnability；
  - 潜在结果框架 → 配对对照与 Neyman 估计；贝叶斯自助法、贝叶斯决策和 Thompson 采样 → 撤出决策。
- 用 "Motivated by [X] \citep{…}, we …" 交代来源。沿用标准目标时可以借 FlowSteer 的句式 "We adopt the standard GRPO objective, modified by one … adaptation"。
- 写清本文改了哪里，以及为什么服务本文的设计。
- 训练目标换名，不和来源同名。
- 新增的 BibTeX 键单独列给用户，由用户从 Google Scholar 取。
- 这里的出处只限理论和通用算法，不包括对比基线（见第 3 节"措辞中立"）。

### 4.4 量的定性

- 相对参考策略的对照量，要写明是 model-relative，不声称是因果效应。
- 正、零、负三种情况可以借 TRACE 的三态句式：positive when …, near zero when …, negative when …。

### 4.5 公式的形式与排版

- 不写 cases 或 if-then 条件式，不做裸列举。嵌套的指示函数改成带标志的插入估计，例如 R²Orch 奖励里的 $c_x$ 和 $\gamma^{h_x}$。
- 相关公式合并，代入已定义的符号。新量在式内用 `\eqqcolon` 定义，例如 $\Delta_k(x)$；同一个量只定义一次。
- 每个展示式在栏内最多两行，能两行放下的不占三行。
- 太长的展示式拆成两个编号公式，中间放第一个公式的释义和一句承接（SkillFlow Eqs. (10)–(11) 体例）。采样分布、闭式解这类细节移到释义里。拆分不改数学。
- 编号不能掉到下一行：公式宽加编号宽不能超过栏宽减 1em。ACL 双栏里，单数字编号时公式宽约 195pt 以内，两位数编号约 190pt 以内。量宽代码和压宽办法见 paper-layout-submission 的"公式编号与留白"。
- underbrace 的标签写成 `_{\smash{\text{…}}}`，不把公式下方撑开。
- 用会议实际字号编译检查（ARR 是 11pt、栏宽 7.7cm），0 overfull。

## 5. 符号与写法检查（每次改方法节后逐条过）

- [ ] **无自指**：不写 $s_t=s_{t-1}\oplus(\dots, f(s_t))$，改成 $f_t=f(s_{t-1},a_t,o_t)$。
- [ ] **不写网络权重**：用 $\mathrm{MLP}_\omega[\cdot]$ 加 "(Appendix~B)"，不写 $W_1,b_1,w_2$。
- [ ] **无硬编码常数**：0.25、8、−0.999 这类数换成符号 $c_{\max}, n_0$，数值进附录配置表。
- [ ] **无伪代码**：不写 `+=` 或给三元组赋值，改成 $W=\sum\indic[b^+>b^-]$ 这类求和。
- [ ] **无同名不同义**：例如 $c_e$ 同时表示违背量和置信度，相邻公式里尤其要查。附录同步改名。又如 R²Orch 的 τ 原先既是轨迹又是 KL 系数，后来轨迹改记 ξ。
- [ ] **每个符号都在 where 句或前文里定义过**，下标的含义一致，例如 $\hat v_\omega$ 和 $\hat v_k$ 的关系写明。
- [ ] **释义和公式一致**：释义里提到的量必须真的出现在公式里，例如不能说"在后向策略下求值"而公式里没有 $P_B$。
- [ ] **术语碰撞已消歧**，首次出现时写清。
- [ ] **每个机制都对得上代码**。代码里没有的机制不写；代码里关闭的功能写"接口保留、本文不评估"。动词也要对得上（chooses 不是 generates）。
- [ ] **公式本身正确**：常数、期望的下标、每条 rollout 读取哪个上下文、计数符号都核对过。
- [ ] **命题与证明一致**：每个正文主张都有所引引理的支持，引理的假设写明且够用，正文和附录的记号一致。
- [ ] **无基线痕迹**：方法节和附录里没有"基于、沿用、用 X 的"，没有基线特有的操作名，tex 注释也清理过。
- [ ] **无不可测量的名字**：不写 task difficulty，写实际的量，例如 "changing $\rho_t$"。
- [ ] **公式排版**：编号没有掉行，展示式不超过两行，0 overfull。
- [ ] 核查结果用一张表交付：公式编号 / 问题 / 原写法 / 建议写法 / 是否动到数学。数学没错的公式不改。

## 6. 方法节的篇幅

- 方法节和预备知识要让"预备知识加方法开头段"在第 3 页结束，第 6 页写到实验节开头。
- 超页时按以下优先级压缩：
  1. 和图重复的流程描述（例如 §4.3 开头段和图 3 面板重复）；
  2. 和公式重复的枚举句；
  3. 动作语义的细节，挪到附录。
- 不删命题，不缩图。
- 改公式省出的行要在同一页补回（例如给证明指针加上引理编号），否则版面会被拉伸出空白（见 paper-layout-submission）。