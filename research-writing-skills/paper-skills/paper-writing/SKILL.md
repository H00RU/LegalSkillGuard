---
name: "paper-writing"
description: "写 ML 会议论文正文（ICLR/NeurIPS/ACL/KDD）：从代码和 idea 提炼创新点与领域级挑战、命名、对照范文逐句仿写摘要/引言/方法/实验，处理外部审稿与 AI 核查意见，以及修改已有段落。写论文、改论文、对齐范文时使用。"
---

# 论文写作：从 idea 到成稿

这套流程来自 EvoSteer、SkillFlow、R²Flow、CollabFlow、R²Orch 等论文的实际写作。核心做法：先定创新点和主线，再以一篇已发表的范文为骨架，逐句对齐改写。改动一律先提议、确认后再落笔。

各部分的细则在分技能里：摘要与引言见 paper-abstract-intro，相关工作、预备知识与方法见 paper-related-method，实验、结论与附录见 paper-experiments-appendix，图表与数据见 paper-figures-data，排版与投稿见 paper-layout-submission。

## 0. 开工前必须拿到的东西

1. **代码或冻结实现**。机制以代码为准（例如 "Mechanisms follow the r24 frozen implementation"）。在 tex 注释里写明依据的是哪个版本。论文与代码大体对得上即可，故事和创新优先。
   - 方法 tex 的文件头写一段实现摘要：每个机制对应哪个代码文件和配置，供核对。
   - 内部代号（例如 ACE）不进正文。
   - 动词和代码一致。例如代码里 Proposer 从候选列表里选题，就写 chooses，不写 generates。
2. **范文源码**。默认用作者自己已发表的论文：FlowSteer 为主，SkillFlow 为辅；领域论文另选同领域范文。要拿 .tex 源码，不要只拿 PDF。
3. **近 1–2 个月的 arXiv 调研**。先调研再下笔，每条文献都要核实存在，不能有幻觉。
4. **目标会议的模板和页数限制**，例如 ICLR 正文 9 页，ACL/ARR 长文 8 页（另有必备的 Limitations）。会议官方模板和官方字体不改动。
5. **实验没做完时可以先写正文**，优先把创新点写出来。实验句里的数字先用占位（例如蓝色方括号），摘要 S7 先不写 significantly，等结果出来再定。

## 1. 提炼创新点

- **数量**：固定三个，结构为"范式 / 支撑对象 / 机制"。
  - 范式：新范式名 + 一句通俗解释。
  - 支撑对象：通常是训练目标，比如 AnchorTB、CTB、R²TB。
  - 机制：建立在上述对象之上的组件，比如 Validated Skill Admission。
  - 先谈范式，再谈机制。
  - 三个创新点可以是同一个整体系统的三个侧面，不硬拆成互不相干的模块。R²Orch 的自博弈和技能脚手架是一套架构，三个创新点分别是范式、向下传目标的训练目标、向上传证据的机制。
  - 工程实现不算创新点，例如分层智能体图、算子画布，放附录。
- **挑战要宽泛**：三个挑战必须是领域里已有工作普遍面临、同行文献已经提出过的问题，每个都能引到文献。不能是只有采用本文机制之后才会出现的窄问题。每个创新点回应一个挑战。
  - R²Orch 初稿的 static curriculum、skill-anchored frontier、success-rate gates 被否，因为它们只在用了本文的两个机制后才出现。
  - 定稿换成 hand-designed curricula、advantage collapse、unreliable evaluation signals，每个都有同行文献支撑。
- **真创新，有理论**：新算法要解决系统自身的问题，有理论基础（例如 GFlowNet、贝叶斯方法、两时间尺度随机逼近），不是超参数或技巧的堆叠。
  - 机制之间互相供给信号，不各自孤立。例如 R²Orch 撤出技能的信号来自同一组 rollout 里的随机对照，不是一个单独的成功率阈值。
- **与范文的可辩护差异**：逐条核对范文的真实定义，比如它的状态里到底有什么，再写差异。在注释里记下：
  - 能主张的差异，例如 "team is running, repair acts on execution"；
  - 不能主张的差异，例如 "Do NOT claim a reward-timing difference: both are terminal-only"。
- **与自己旧作区分**：借用自己旧作的组件（例如 TB/SubTB）时，必须改写成服务本文设计的形式并换名。三个创新点里，至多一个可以和旧作合并算。
- **与对比基线的关系（硬规则，用户定为非常严重）**：
  - 即使代码借用了某个对比基线的实现或想法，论文里也不写方法基于它、沿用它，或是几个基线的结合。正文、附录、图中文字、tex 注释都一样。
  - 反例："skills are edited with the PATS editor"、"R²Orch combines SESA's and PATS's loops"。
  - 基线只出现在引言、相关工作和实验的对比里。借来的实现细节用中性描述放附录（见 paper-experiments-appendix 第 7 节）。
  - 理论基础和通用算法不受此限，例如 SubTB、两时间尺度随机逼近、贝叶斯决策，可以写 Motivated by 或 following，并按第 2 节的技巧命名。
- **一条主线**：全文只有一条主线，各组件都要融进去，不能写成三个互不相干的部分。主线要像系统本来就有的设计，不是事后加的外壳。
  - EvoSteer 的主线："看起来对，但价值估计说会失败"。
  - R²Flow/CollabFlow 的主线：RSI。
  - R²Orch 的主线：两层 RSI，一个 RSI 过程改进整个 RSI 系统。
  - 图 1、案例研究、实验结论都要服务主线。
  - 主线在固定位置各出现一次：摘要 S3/S6、引言 P5、图 1 图注、方法 4.1 开头，不反复重申。
- **成本**：方法的 token 和墙钟开销要和对比方法同一量级。成本问题在理论或设计层面解决。
- **理论**：理论要有文献背书，缺理论就去找文献。命题用一句白话陈述，证明放附录。命题只说附录真正证明了的内容。

## 2. 命名规则

- 撞名是大忌。不能和已有方法或目标同名，近似的也要换成好记、好对比的名字。
- **命名技巧（用户要求永久记住）**：先找创新点所依托的基础算法或理论，再以它的扩展或改进来命名，例如 R²TB 扩展 SubTB、SkillFlow 的 TTB。不凭空造描述性名字。
- 自创名字全文控制在 3–4 个，其余术语一律用同行常用说法。例如用 "communication graph"，不用自造的 "team graph"。
- 方法名和题目不要塞过细的技术名，例如 Sub-Trajectory Balance、Balance。副标题要通俗直白。
- 不要用会误导的 ML 术语。例如 "calibrated" 在 ML 里指置信度校准，不能挪作他用。
- 不用学术里不通用、读起来别扭的词。例如 sibling（兄弟组），R²Orch 全文删掉了。
- 不要给无法测量的东西命名，例如"任务难度"。写实际计算的量。
- 命名尽量和题目呼应。例如 CollabFlow 里各组件名都带 Collab。
- 题目要带出主线。例如 R²Orch 的题目带出了两层 RSI、编排、自博弈和技能内化。
- 改名后（例如 R-PlayFlow → PRFlow → R²Orch）全局搜旧名，正文、图中文字、中文版、注释、文件名都要换。

## 3. 逐句对齐范文（核心方法）

1. 把范文每一部分拆成句子，记下每句的功能模板和词数。
2. 在本文 tex 里每句前写注释，例如：
   - `% S3 [31w] "To address these challenges, we propose NAME, a new paradigm of P---gloss."`
   - 段落级写 `% P4 [155-222w] "However, these methods still face three challenges. (i)..."`。
3. 按模板写本文句子：功能一致，词数接近。
   - 在文件头记录总词数和范文的差距，例如 "total 204w against FlowSteer's 162w"。
   - 超出时逐句压缩，不整段删。
   - 词数用脚本回填到注释里，不手数。
4. 句子级的约束和禁区也写进注释（见上面的 Do NOT claim），后续修改不会踩线。
5. 用户要求对照时，给出逐句对照表：范文句 / 本文句 / 各自词数 / 多写或少写了什么。
6. 对齐稿开头放一张对应表：挑战 / 对应创新 / 摘要句 / 引言 P5 句 / 方法小节 / 命题白话（格式见 paper-abstract-intro 第 0 节）。

## 4. 各部分模板（FlowSteer / SkillFlow 体例）

### 摘要（8 句）

| 句 | 词数 | 模板 |
|---|---|---|
| S1 | ~18w | In recent years, X have been widely applied to Y. |
| S2 | ~42w | However, existing X still faces key challenges, including *A* that…, *B* that…, and *C* that…（三个挑战用斜体命名，与引言 P4 同名） |
| S3 | ~30w | To address these challenges, we propose NAME, a new paradigm of P---gloss. |
| S4 | ~30w | To support this paradigm, we introduce *OBJECT* (ABBR), a … that … |
| S5 | ~35w | Built on …, we further propose *MECHANISM*, in which … |
| S6 | ~20w | Moreover, … |
| S7 | ~22w | Experimental results on N datasets show that NAME significantly outperforms baselines across … |
| S8 | ~6w | Our code is available at … |

摘要里不用否定句式。实验结果出来之前，S7 不写 significantly（R²Orch 定稿用 consistently）。

### 引言（6 段）

| 段 | 词数 | 内容 |
|---|---|---|
| P1 | 1 句，32–48w | In recent years, a variety of powerful … |
| P2 | 2 句，约 70–90w | In this process, X has become a key bridge … However, in practice, … |
| P3 | 4 句，约 70–150w | To address these issues, three main lines of work have emerged (Fig. 2). First / Second / Third，各带引用 |
| P4 | 约 155–222w | However, these methods still face three challenges. **(i) 名称.** … **(ii)** … **(iii)** …；名称和摘要 S2 一致 |
| P5 | 约 137–218w | To address these challenges, we propose **NAME** …；展开摘要 S3–S6 |
| P6 | 2–4 句，约 69–93w | We evaluate on benchmarks across … Results show …；最后半句点题 |

- 贡献与挑战逐句一一对应：范式对挑战一，目标对挑战二，机制对挑战三，"此外"句也要能对上。
- 挑战必须是领域级的宽泛问题（见第 1 节）。
- 贡献不能写成工程描述。例如"通信边汇聚证据、写权限保证可串行化""同一框架支持三类团队"这种写法要删掉。
- 改了引言，摘要要同步改。

### 相关工作

- 固定两段，加粗段首标题，例如 Agent Task Orchestration、Skill Self-Evolution。
- 按类别合并、分组引用，不逐篇讨论（EvoSteer、SkillFlow 体例）。
- 每段末尾用一句话说清本文做法的不同，不贬低他人。
- 必须留在正文，不能移到附录。

### 预备知识

- Definition 1：对象（图）。
- Definition 2：轨迹。
- Problem Statement：目标分布公式加 where 句。
- 每块词数对齐范文，例如 Def.1 约 66w、Problem 约 88–123w。
- 工程对象（例如算子画布）放附录，正文只要对象、轨迹和部署目标。

### 方法（SkillFlow Sec. 4 体例）

- 开头一句路线图："As illustrated in Figure 3, this section introduces … (Section 4.1), … (4.2), and … (4.3)"。
- 每个 4.x 开头先说目的，再讲机制。小节内用加粗 run-in 段首，不用 \subsubsection。
- 每块的写法：引导句以冒号结尾，接编号公式，再接一句 "where …" 解释。解释句 13–23 词，平均句长 15–20 词。
- 借用的条件用括号里的形容词交代，不写防御性的对比句。
- 每个公式从一个权威理论结果出发，再写本文改了什么（SkillFlow TTB 体例）。
- 每个小节恰好一个 Proposition，放在小节最后。命题是一句不带数学的白话，紧跟 `\emph{Proof.} Appendix~X`，证明指针写出依据的引理。命题下面不再放任何内容。
- 附录指引放括号里，不单独成句。
- 超参数尽量不进正文。
- 讲解方法时用白话和小例子，不堆公式。
- 方法顺序：4.1 建模与范式（突出范式自身的要素），4.2 目标或机制，4.3 训练或机制。
- 方法节不点名、不致谢对比基线。公式排版、措辞中立和符号检查见 paper-related-method。

### 实验

- RQ 围绕正文创新点设计（RQ 可以改，用来服务创新点）。典型安排：
  - RQ1 分布内对比；RQ2 分布外泛化；RQ3 跨执行器迁移；
  - RQ4 组件贡献；RQ5 目标对比与机制按设计工作。
  - 也可以每个创新点一个 RQ。R²Orch：RQ1 主结果，RQ2 骨干迁移，RQ3–RQ5 各对应方法 4.1–4.3。
- 指标要直观：准确率、计数、曲线。不用秩相关、采样比例这类晦涩指标。
- 设置部分写得简短，细节交给附录。用加粗段首（Datasets / Baselines），不开 5.1/5.2 小节也行。
- 每个结论段按"结论 → 原因 → 证据"写：讲清为什么赢，原因落到创新点上。只复述表中现象的段落会被整段退回。挑关键数字，不堆数字。
- 主结果段解释本文为什么胜过所有对比方法家族，不单挑某个基线，也不写"本文是最强基线的结合"。
- 写法示例（R²Orch RQ3）："Both loops are needed (Table 2): skills give the Director the early successes that make hard tasks learnable, and the Proposer keeps groups away from uniform outcomes."
- 结果段不放引用，数据集和基线的引用、配置细节放附录 D。图注、表注要简洁，不堆引用。
- 主结果表里和外部方法的比较少而精，和以前的论文一样，不堆很多外部基线。
- 每张数据图用不同的图型，不重复用几张热力图。IID/OOD 泛化图的老模板在几篇论文里都用过，审稿人能认出来，要换新模板；先给 2–3 个方案对比，例如 R²Orch 的图 4 试过哑铃图、斜率图和散点图。
- 段落细则见 paper-experiments-appendix。

### 案例研究（附录）

- 只选能体现主线的案例，例如"表面全对，价值估计骤降，重跑后修正"。
- 段首写 `Key Observations:`。
- 确认案例数据没有泄漏，例如测试题出现在训练集里。不确定就问用户；用户说删就删。

### 结论

- 2 句，约 40 词。页数紧时可以更短，R²Orch 是 29 词、不超过四行，空间让给实验。
- 结论和各 RQ 的口径一致。例如 RQ 改成"不再帮助时撤出"后，结论也写 "retires skills that stop helping"。

### ACL 收尾三节（结论之后，不计页数）

- **Limitations**（必须有）：如实写真正的局限。R²Orch 只写了一条："初始技能按数据集手工定制，新领域怎样自动得到初始技能仍是开放问题"。
- **Ethical considerations**：用公开基准，按原作者的用途使用，没有人类受试者和个人数据；能调用工具的智能体有被滥用的风险，所以开源代码供检查，并建议在沙箱里运行。
- **Acknowledgements**：如实写 AI 助手的用途（例如润色、LaTeX 排版），作者对内容负全责。

## 5. 风格硬规则

- 不过度宣称：小数据集不说 large-scale，"first" 要限定范围。
- 不做防御性限定，比如 "we only prove X / do not prove Y"，结果正面陈述。
- 同一主张或限定语不要反复出现，反复会显得防御且像 AI 写的。收紧时调整措辞、删重复，不要大幅压缩内容。
- 写清楚与前人"做了什么不同"，正文和图都要体现，不贬低他人。
- 不把方法写成对比基线的组合，也不写建立在某个基线之上（见第 1 节）。改完在 PDF 文本里搜一遍基线名，剩下的只能是对比用法。
- 结论的强度要配得上证据。例如证据只说明"不再帮助"，就不写"已内化"。
- 正文只引用必要文献，附录一般不放引用。每条参考文献都必须在正文被引用。

## 6. 修改已有文本（非常重要）

1. 先通读，弄清每句话说什么、有多少词，再动手。
2. 一次只改一句：保留句子结构和大致词数，只改需要改的地方。打乱作者原有句子和风格是严重伤害。
3. 先提议后修改：先列出"原句 → 新句 + 理由"，等确认后再应用，不要一次改一大批。
4. 填孤行或补短页时，素材取自项目自己更早、更长的旧稿（例如 `*.pre-compress` 备份），不新写内容。可以把已有内容说得更清楚，不添加新主张。
5. 用户说"改得有问题"时，整体回退到改写前的快照，再按用户自己的版本重做。所以每轮大改前都要存快照。
6. 只改确有问题的地方。用户或外部意见指出的问题，先核实是否真的存在；不存在就说明理由，不改。用户原话："你确定问题了再修改"。
7. 范围纪律：用户说只改什么，就只改什么。例如"只还原图，不动文字"。
8. 改词或删句之后，检查段尾孤行和正文末页，必要时换成等长的说法（见 paper-layout-submission）。
9. 用户说以后还要更新版本时，先存源码快照，旧版 PDF 另存归档，不覆盖。
10. 用户常用语音输入，同音错字按上下文理解。例如"不利名"是署名，"不懂文字"是不动文字，"CATS"是 PATS。拿不准时在回复里用一句话说明自己的理解。

## 7. 外部审稿与 AI 核查意见

1. **逐条独立判断，不照单全收**。外部 AI（Codex、GPT 等）的意见只是提示可能的问题。
   - 它们常带过度防御或过度条件化的写法，例如 "only when X can Y"、"若……则……，并须承认不保证……"。
   - 也常要求另起一套统计框架，例如漂移上界、置信序列、层次模型、频率学保证。
2. **核实依据**：论文源码、冻结代码、建表脚本、训练日志，以及自己复算的反例。每条判为成立、部分成立、不采纳或不适用，写出依据和处理方式。
3. **处理原则**：
   - 文字和代码或证明对不上：照实际实现改文字，不为此重跑。需要重跑的代码层修复不进论文，记下来留给以后。
   - 命题超出了证明：换成能严格证明的正面陈述，保留创新点，让每句话正好说附录证明的内容。不改成"若……则……，不保证……"。
   - 要求另起统计框架：不采纳，只把估计对象写准，例如"在检验过该技能的任务上的后验期望代价"。
   - 用户说不写的就不写，例如五次运行的具体定义、早期设置的差异、恢复了几次。代码里已开源的细节（例如检索工具）可以不补写。
4. **交付格式**：
   - 先给一张"条目 / 判断 / 依据 / 处理"表；
   - 再给修改清单：原句 / 新句 / 理由，英中各一条，每个原句在源码里恰好匹配一次；
   - 然后列不采纳的条目和理由、在副本上试编译的结果（页数、overfull、孤行），以及需要你确认的点；
   - 数据类意见的核实见 paper-figures-data 的 F 节。
5. **送外部 AI 核查之前**，附一份 README：理论在哪几节；建议核查哪几项（公式是否正确、引理假设是否写明且够用、正文主张是否有引理支持、正文和附录记号是否一致、说法是否和代码一致）；并写明实验数字不在核查范围内。

## 8. 中英双版

- 每次交付论文，都把英文 PDF 和中文 PDF 一起给。例外：
  - 纯排版轮（调孤行、调间距、参考文献）只更新英文，中文不动；
  - 用户明确说只要英文或只要中文时，按最新的指示；
  - 用户说署名版不再更新后，只更新匿名版。
- 中文版放在 `sections-zh/`，和英文逐段对应。改英文时同步改中文，数字必须完全一致。
- 中文版配一份术语表（GLOSSARY.md）和翻译规则（TRANSLATE-RULES.md）：
  - 逐句忠实，不增不删，不加解释和防御措辞；
  - LaTeX 命令、数学式、引用键、数字原样保留，去掉汉字后的 LaTeX 骨架和英文一致；
  - 数据图文件名的 _en 改成 _zh。
- 可以把各节分给子代理并行翻译，每个只写自己的输出文件。回收后核对数字、cite/ref/label 的个数和有没有破折号，再编译。
- 中文写作不用破折号，改用短句。
- 回复用户用简洁中文，不用破折号。