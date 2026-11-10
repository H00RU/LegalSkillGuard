# 外部法律技能共同修订：查新记录

日期：2026-11-11。下面均打开了论文 primary 全文/官方论文页。结论针对查到的方法机制，不能据此宣称全世界无人做过。检索覆盖 agent skills、memory repair、program repair；特别补查 2026-10/11 新近工作。

## 1. 最关键近邻

| 工作与 primary | 核实的方法位置 | 已经做了什么 | 本项必须增加什么 |
|---|---|---|---|
| [DiscernMem](https://arxiv.org/html/2610.36652v1) | §3 DMR/BLM；限制讨论；附录回放 | 单记忆与无记忆匹配回放，区分规则缺陷和误用，验证当前及旧任务；作者明确指出隔离修复不能解决多规则共同依赖 | 多个既有技能的旧/新版本实测，识别最小共同修改块，而非更多单条回放 |
| [EviSkill](https://arxiv.org/html/2610.05030v1) | §3.1–3.3；附录 D.1–D.2 | 编辑—证据卡、回放验证、暂存编辑跨 epoch 传播；整修订被拒后仍保留有用编辑；附录确实检验了教师挑出的联合编辑子集 | 系统检验未独立改善的互补修订，学习带上下文的修订依赖；不能声称它从不组合 |
| [Skill-V](https://arxiv.org/html/2610.11781v1) | §3.2–3.4，尤其 §3.3 | 版本化可证伪契约，rubric 与环境结果比较，保持语义约束和历史证据；逐技能边界更新 | 用实际新旧版本交叉执行建立共同修订证据；rubric pass 不等于新的执行已正确 |
| [EvoSkill v2](https://arxiv.org/html/2610.25931v1) | §3.3、§6.3–6.4 | 冻结 solver，stateful evolver 读取多次轨迹改整库，接受每个 epoch 更新以避免噪声 gate 错拒 | 不能以“允许联合修改”胜过它；要比较结构化修订依赖是否用更少执行发现好包 |
| [EvoSkill](https://arxiv.org/html/2603.02766v1) | §2.1–2.3 | 教师分析失败与 gold，技能创建/编辑，维护高分整库 frontier 和反馈史 | 固定候选下的包级强对照必须保留其整库评价、历史反馈能力 |
| [DGM](https://arxiv.org/html/2505.22954v3) | §3，附录算法 | 冻结 foundation model，自改代码，保留可运行的版本档案，允许暂时低分的 stepping stones | 不可声称首次跨越更新低谷；区别是具法律语义条件的共同修订关系作为可复用学习对象 |
| [Multi2Fixer，ASE 2026](https://arxiv.org/html/2607.26591v1) | §3.3.3 hunk scheduling/patch selection；§3.3.4 refinement | 建立带类型和置信度的 hunk dependency graph，逐次更新，协调变更传播并可回访先前编辑；整包编译/测试修复 | 不可主张首次协调依赖修改或学习修订图。需要检验 fixed-case 混合版本实验支持的跨法源义务迁移经验是否有独立收益 |

DiscernMem 提供了最直接的问题证据。Skill-V 也明确承认完整轨迹结果不能确定某个技能导致成败。EviSkill 与 DGM 则证明：本方案若退化为“保留拒绝版本以后再试”就没有足够差异。

## 2. 技能交互、因果检索和法律近邻

| 工作与 primary | 已核实范围 | 对当前设计的约束 |
|---|---|---|
| [CaSKG](https://arxiv.org/html/2608.25500v1) | §3.3 对技能描述作移除、替换、换序的文本反事实；§3.4 校准边；§3.5 检索 | “反事实技能关系”已有人做；不能把相关边改名因果边。本项做可执行 old/new revision 兼容及修订生成，不只检索 |
| [ASSAY](https://arxiv.org/html/2606.15390v1) | §2.1 随机掩码估计每技能效果；§2.2 重构；§2.3 每任务屏蔽 | 不能把逐技能因果归因当创新；必须和允许掩码解决问题的同库对照比较 |
| [SkillGraph](https://arxiv.org/html/2605.12039v1) | §3.1–3.3 prerequisite/enhancement/co-occurrence 图，节点插入/合并/拆分/废弃和边更新 | 图组织和依赖检索已存在；本方法边是特定修订的兼容条件，不是技能使用先后边 |
| [KDASO](https://arxiv.org/html/2611.06972v1) | §4.1 三类邻域归纳，§4.2 与专家轨迹对齐，§4.3 预算 routing | 已经在法律责任裁决中学习和改进技能，不能主张首次法律技能学习。需要靠共同修订机制及实测差异支持贡献 |
| [Scope Before You Persist](https://arxiv.org/html/2609.29144v1) | §3.2 家族槽，§4 匹配回放和多证据 gate | scope 隔离和非回归门已经存在；仅给法律来源加域标签、版本和历史回放不够 |

ASSAY 的随机掩码本身包含其他技能联用上下文，不能误写它完全忽略交互；它最后估计与使用的核心量是单技能平均效应。CaSKG 用文本 probe，不等同于我们 proposed 的固定案件下真实新/旧技能执行矩阵。两者仍能用掩码/检索解决部分同样失败，必须纳入强对照。

## 3. 通用外部学习和进化框架

| 工作与 primary | 查明机制 | 不能作为本项新增的部分 |
|---|---|---|
| [ACE](https://arxiv.org/html/2510.04618v2) | §3.1 itemized delta updates；§3.2 grow/refine；生成、反思、整理分工 | 增量编辑、保留细节、累计文本 playbook |
| [ExpeL](https://ojs.aaai.org/index.php/AAAI/article/download/29936/31635) | 成功/失败经验提炼，自然语言 insight 调整，测试检索 | 冻结模型从失败经验中学文本规则 |
| [SkillWeaver](https://arxiv.org/html/2504.07079v1) | §2 propose/practice/synthesize/hone，API 测试与调试；简单到复杂组合 | 可调用技能、教师生成代码、实践验证和反复改进 |
| [SkillRL](https://arxiv.org/html/2602.08234v1) | §3.1–3.3 分层 SkillBank，失败驱动递归进化，与 RL 联训 | 技能层次、失败归纳、教师参与；其参数联训不适合直接作为本项目主路线 |
| [EvolveR](https://arxiv.org/html/2510.16079v1) | §3.2 离线自蒸馏原则、去重/动态评分；§3.3 policy RL | 经验闭环、原则库、质量分数 |
| [MemEvolve](https://arxiv.org/html/2512.18746v1) | §4.1–4.2 内部记忆演化+外部架构诊断重设计，Pareto 选父代 | 优化 encode/update/retrieve/manage 架构，不能把换存储结构说独立方法 |
| [SkillForge](https://arxiv.org/html/2608.24747v1) | §3.3 真实调用统计、EMA 成功率、教师反思修订；限制中教师依赖 | 记录每次调用、统计技能成功率、低分触发反思 |

## 4. 程序库学习与多编辑修复：不是可表达性就否定，但要正面对比

[Stitch](https://mlb2251.github.io/stitch.pdf) 和 [BABBLE](https://ztatlock.net/pubs/2023-popl-babble/) 解决可复用程序抽象/库压缩；[Refazer](https://www.microsoft.com/en-us/research/wp-content/uploads/2017/04/icse2017-refactoring.pdf) 与 [Getafix](https://arxiv.org/pdf/1902.06111) 学习代码变换与上下文模式。当前方法不能把几个 AST rewrite、反统一或保存技能片段算新颖。

[Variational Execution for Automatic Program Repair and Higher Order Mutation Testing](https://www.cs.cmu.edu/~chupanw/papers/fsenier18.pdf) 已明确讨论联合候选修改的交互及多编辑补丁。版本组合测试、无效配置约束、MaxSAT 最小修改和原子提交均是成熟组件。单纯把这些接到外部技能库，不足以支持算法首创。

这不意味着通用程序修复“能表达同一个结果”便自动否决领域方法。需要检查的是本设计**实际新增的选择和更新行为**：它是否从法律命题的变化及其下游使用中学到了可复用的伴随修订规律，并在新来源上用该规律更快生成正确修订包。普通包级搜索必须获得相同候选、标签、回放池和最多三项编辑能力；普通约束修复还应获得相同版本表。若两者已经做到同样的工作，本项就只剩工程组合。

最强组合基线需为 **Multi2Fixer 式依赖协调 + Getafix/Refazer 式多位置历史编辑模式 + 相同可用 native tests**，不能仅拿无记忆贪心修复来比较。M2 的独立控制变量是：完整交叉执行产生的“联合必要/单改充分/联合有害”证据，是否真正改变跨法源的伴随修改生成。依赖图字段、MaxSAT、计数排名都不是独立新算法。若这一控制变量无实际收益，不能仅凭法律应用场景声称两个扎实方法已成立。

## 5. 本轮推荐与可写主张

推荐把“法律技能共同修订关系学习”作为独立于单项技能获取的第二项实现目标。其理由是有明确原任务问题、可观测更新单位、可运行判定、可复用学习产物和强对照，而不是一条泛泛的“让技能协作更好”。

可写：提出一种面向法律技能互补修订的外部学习机制，通过固定案件的新旧版本交叉执行识别修订依赖，并将其用于后续伴随修订生成。

当前不可写：首次允许联合修改；已有方法均逐条贪心；已经证明新颖性；已经证明五库有效；单个混合版本失败就证明跨所有法源的普遍依赖；上述有限构造就是原始数据中的真实失败。

详细算法、有限真值表、适用数据与强对照见 `METHOD_EVOLUTION.md`。本轮未调用执行模型或教师，未修改远端。
