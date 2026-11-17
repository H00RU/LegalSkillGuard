# 查新综合与二次排重记录

截止 2026-11-17；不按篇数封顶。围绕“读者条件接口学习”“技能更新监督”“不完备语义与关系测试”“真实法律任务”检索，并向基础理论回溯。以下分别标出最近邻的方法证据与用于限定边界的背景证据；不是声称每篇全文所有实验均已复现。

## 研究问题与综合判断

RQ1：现有方法是否已能学习适合弱模型的任务表示？能。PARSE、SCOPE、Pix2Pred 等使“弱模型友好的分解/接口”本身没有独占新意。方法一保留的对象是固定法律消费者的非可逆关系接口及其配套消费者合成，并在合法候选中按真实冻结读者选择。

RQ2：现有方法是否已能用反例/干预改技能？能。DAAF、GraphSkillAA、SkillEvoReg，以及法律领域 Synedrion 已覆盖大部分常见表述。方法二保留的是不完整源语义下自动合成共享解释的关系监督，处理合法源变化、未改事实的共享范围、派生字段和跨例相关性。

RQ3：相邻工作说明问题存在，是否足以证明我们的创新？不足。现有局限只用于选问题；差异须落实到学习对象、输入假设、求解过程及公平对照。可由通用程序/SMT表达不自动构成重复；反过来，换成法律数据和冻结参数也不自动构成新机制。

## 一、执行表示与接口学习

| 已核实原文 | 已有内容与证据范围 | 本方案差异及必须比较的内容 |
|---|---|---|
| [PARSE，EMNLP Industry 2025](https://aclanthology.org/2025.emnlp-industry.184/)；[方法 §3.1](https://arxiv.org/html/2510.08623v1) | ARCHITECT优化schema，RELAY恢复原schema；已读方法与附录转换实例 | 允许非可逆丢弃不影响消费者的信息。接口+decoder并非首次；PARSE+相同参考/预算是强对照。 |
| [SCOPE，Mazza、Levi，2026](https://arxiv.org/html/2610.31062v1) | §3：冻结弱模型回答谓词，Python组合，教师优化程序并生成反例；无reasoning执行已明确 | 不把分解/教师/弱模型组合当创新；比较固定消费者约束下的候选合成与自由程序优化。 |
| [Pix2Pred，Athalye等](https://arxiv.org/html/2501.00296v4) | 原文中的VLM谓词提出/评估、下游规划选择 | 不能主张首次用固定基础模型读取学习出的谓词；法律消费者固定且要求精确配套变换。 |
| [Predicate Invention for Bilevel Planning，AAAI 2023](https://ojs.aaai.org/index.php/AAAI/article/view/26429) | 谓词语法与下游规划效用 | 下游驱动抽象已知；本项应证明读者误差与消费者约束共同作用。 |
| [WebQA，PLDI 2021](https://pldi21.sigplan.org/details/pldi-2021-papers/22/Web-Question-Answering-with-Neurosymbolic-Program-Synthesis) | 冻结NLP模块及DSL程序学习；官方论文页与方法描述 | 神经模块+符号合成不新；联合改变接口并保持固定消费者是新增对象。 |
| [Atlas，CAV 2018](https://web.eecs.umich.edu/~xwangsd/pubs/cav18.pdf) | 反例驱动抽象/变换器学习 | 不能认领CEGAR或抽象模板新理论；比较实际生成过程而非名字。 |
| [Functional Compression through Graph Coloring](https://bpb-us-e1.wpmucdn.com/sites.mit.edu/dist/2/1652/files/2025/05/Functional-compression-through-graph-coloring.pdf) | 函数所需信息、编码和图着色 | 充分性数学已知。自然语言读者非可靠编码器，真实读者误差必须进入训练。 |
| [Text-to-SQL Friendly Logical Database Design，2026](https://arxiv.org/abs/2606.03145) | 摘要/设计概述：语义保持的视图、分区、命名优化LLM查询 | 不能说经典变换+LLM友好首次；区别是原文事实读取及消费者充分的不可逆关系。 |
| [ScheMatiQ，ACL Demo 2026](https://aclanthology.org/2026.acl-demo.22.pdf) | 问题驱动schema与源证据抽取 | 任务相关schema、法律场景、源证据都不是独立新点。 |
| [From Weak Task Specifications to Scientific Extraction Agents，2026](https://arxiv.org/html/2609.34829v1) | schema/指令共同优化与失败反馈 | 共同优化本身不新；本项新增受消费者语义限制的合成空间。 |

## 二、技能更新、错误归因与关系监督

| 已核实原文 | 已经做了什么 | 本方案需要超出的地方 |
|---|---|---|
| [GraphSkillAA，2026，v3](https://arxiv.org/html/2609.20455v3) | 技能图局部更新、失败分类、NO_PATCH、回滚；H.3讨论干预检验归因 | 不能把该文的未来工作当全领域空白；更近的DAAF已经做干预。 |
| [DAAF，Yuan等，2026](https://arxiv.org/html/2609.32498v1) | §3对版本化资产的注册替换回放，用原生任务结果学习单项/联合效果 | 本项生成其所需训练证据及部分监督；不是另起一个更新信用预测器。 |
| [SkillEvoReg，Nie等，2026](https://arxiv.org/html/2609.30861v1) | §4.4/附D：候选语义变化驱动源攻击，旧新技能共同验证，含Law域oracle | 候选驱动源对和四格回归已有；新增必须是共享未决语义下的允许关系自动合成。 |
| [Synedrion / An LLM Agentic Approach for Legal-Critical Software，ICSE 2026](https://arxiv.org/html/2509.13471v2) | §2/3.2：法律高阶蜕变关系、税法程序生成和反例修复 | 不能主张无绝对标签的法律测试首次。本项从部分语义约束合成关系，而非由LLM直接推定关系。给同样语义输入作对照。 |
| [NormWorlds-CF，2026](https://arxiv.org/html/2607.03957v2) | §2：完整可执行规范世界、成对变更、确定结构标签及关系奖励 | 本项源语义不完整，输出是共享完成下的允许关系集合；冻结参数只是路线约束，不是新颖性。 |
| [A³BL，He等，ICML 2024](https://proceedings.mlr.press/v235/he24j.html) | 多个溯因候选的歧义学习，官方页与论文 | 多解释保留已知；本项生成新源组及其跨例监督，不把一个解释变成伪金标。 |
| [MRFR/GCJR，2026](https://arxiv.org/html/2608.29228v2) | 最小联合成功恢复修补集；依赖干净替换消息的受控设置 | 本项没有干净中间消息oracle；不声称枚举所有修补首次。 |
| [Retaining Repair Hypotheses for Cost-Aware Execution，2026](https://arxiv.org/html/2610.39410v1) | 修补假设、信息选择、成本感知执行 | 通用主动诊断可完全吸收旧“按更新类选问”草案，已排除该主张。 |
| [Oracle-Guided Component-Based Program Synthesis，Jha等，ICSE 2010](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2010/EECS-2010-15.pdf) | 区分候选程序的输入合成 | 区分输入与SMT不归为首次；对象必须包含自然源变化、共享变量和部分关系监督的编译。 |
| [Metamorphic Testing and Debugging of Tax Preparation Software，ICSE 2023](https://ashutoshtrivedi.com/assets/papers/2023-icse-seis-tax-prep.pdf) | 法律税务关系oracle及调试 | 税法关系、单调性、免oracle验证本身不新。 |

## 三、问题与数据适配证据

| 原文 | 相关结论与用途 |
|---|---|
| [Know Your Limits，2026](https://arxiv.org/html/2606.16118v1) | 法律任务严格蕴涵与语用条件差异；支持先校准任务契约，不把默认条件遗漏当方法贡献。 |
| [Open-World LLM Logical Reasoning，ICML 2026](https://proceedings.mlr.press/v306/mo26f.html) | 求解器找缺失前提与逻辑/事实双验证；排除泛泛“阻断补读”作为新第二项。 |
| [CROWN-QA / When Absence Is Evidence，2026](https://arxiv.org/abs/2608.04591) | 覆盖范围影响缺失证据的解释；背景核验，不据摘要虚构量化优势。 |
| [DeonticBench，2026](https://arxiv.org/html/2604.04443v1) | 公开规则任务及参考Prolog；Housing来源独立于SARA/Airline。新方案仅选数据路线，未声称已锁定划分。 |
| [RuleArena，ACL 2025，官方仓库](https://github.com/SkyRiver-2000/RuleArena) | 数值政策计算及原生程序；本包真实TRAIN原型使用其Airline评分代码，保留MIT许可。 |

这些文献的指标不能作为“我们的分数必须达到多少”的直接阈值：任务、模型、分布与标注不同。方法差异应通过同源、同预算、同模型的实验确认。近邻中的预印本按预印本处理，不以其未审核结果作顶会录用背书。

## 四、评估后再次排重

先按 idea-evaluator 评估具体算法，再补查：`consumer-preserving/neural interface`、`non-invertible schema LLM`、`shared interpretation skill learning`、`partial specification metamorphic legal`；同时回读 PARSE §3.1、SCOPE §3、DAAF §3、SkillEvoReg §4.4/附D、Synedrion §2/3.2、NormWorlds-CF §2 及抽象学习近邻。精确关键词没有命中不视为新颖性证据，判断主要依据上述方法对照。

最终保留的完整机制未检索到直接重复实现。已确认重复的宽表述全部剔除：弱模型分解、schema优化、反例生成、干预归因、联合修补、回滚、保留歧义和蜕变测试。两项是这些领域中的具体方法推进，不能写成首次提出全部基础思想。

## 五、检索与证据边界

本轮重点核查了与设计相关的代码闭包、TRAIN原始记录和历史来源级诊断，不声称逐条复审仓库所有历史调用。有限原型全部0模型调用。复审框架由本助手执行，不是港科大机构或专家审稿背书。确定性原型证明设计可运行；论文效果必须由后续固定真实研究证明。
