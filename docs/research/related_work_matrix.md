# LegalSkillEvolve相关工作与方法边界

> 核验日期：2026-09-24。本表区分“论文应讨论的相关工作”“主表直接基线”和“真正进入现役实现的机制”。文献数量多不等于系统组件也应多；现役实现只吸收能回答当前研究问题且不破坏干预隔离的机制。

## 研究定位

LegalSkillEvolve研究的是：冻结小模型能否从同案K=4多轮法律咨询轨迹中归纳并持续局部更新一份外部自然语言playbook，从而以更少提问获得更多关键事实。它不是模型权重强化学习、法律RAG、任意工具调用agent，也不是把强模型答案直接蒸馏给弱模型。

## 相关工作分层

| 谱系 | 代表工作 | 与本项目的关系 | 现役实现取舍 |
|---|---|---|---|
| 无权重经验学习 | [ExpeL](https://arxiv.org/abs/2308.10144)、[AutoGuide](https://arxiv.org/abs/2403.08978)、[Agent Workflow Memory](https://arxiv.org/abs/2409.07429) | 从成功/失败经验提炼insight、条件化guideline或workflow，并在后续任务复用 | ExpeL-adapted作为主表基线；不增加在线检索模型，避免把收益混同于路由器能力 |
| 技能库与持续学习 | [Voyager](https://arxiv.org/abs/2305.16291)、[SAGE](https://aclanthology.org/2026.acl-long.69/)、[SkillRL](https://arxiv.org/abs/2602.08234)、[SkillX](https://arxiv.org/abs/2604.04804) | 说明可解释技能库可积累、复用和迁移；也展示顺序rollout、层级技能及技能扩展 | 保留“外部可审计知识状态”和顺序积累；不照搬代码技能、权重RL或三层技能库，因为本任务动作空间是语言咨询且数据规模较小 |
| 跨轨迹技能抽象 | [SkillLens](https://arxiv.org/abs/2605.23899)、[Trace2Skill](https://arxiv.org/abs/2603.25158) | 直接研究经验生成—技能抽取—技能消费链；强调成功与失败混合经验、逐轨迹/分包抽取以及跨轨迹层次归并 | 现役的“双map抽取 + 单reduce归并”主要受此启发；全部健康K组必须被引用或显式记为无新增，避免只挑少数好看的案例 |
| 文本空间优化与抗遗忘 | [Dynamic Cheatsheet](https://arxiv.org/abs/2504.07952)、[ACE](https://arxiv.org/abs/2510.04618)、[SkillOpt](https://arxiv.org/abs/2605.23904)、[SkillAdaptor](https://arxiv.org/abs/2606.01311) | 把提示、上下文或技能文档作为可训练状态，利用反馈做增量或有界编辑 | 采用稳定ID、精确ADD/REPLACE/DELETE和未命中条款保留；不采用逐候选小样本效果否决，也不整份自由重写 |
| 技能评测与组合 | [SkillLens效用研究](https://microsoft.github.io/SkillLens/)、[SkillComposer](https://arxiv.org/abs/2606.32025) | 区分技能“看起来合理”和真实下游效用，并研究多技能选择/组合的上下文成本 | 本项目最终以同案Base/静态技能/ExpeL/Ours实测，不以教师自评代替效用；当前只注入一份紧凑playbook，避免路由与组合成为额外变量 |
| 法律多轮咨询评测 | [DLawBench](https://arxiv.org/abs/2606.13931)、[LeCoDe](https://arxiv.org/abs/2505.19667)、[LexRAG](https://arxiv.org/abs/2502.20640)、[J1-Bench](https://aclanthology.org/2026.acl-long.471/) | 提供隐藏事实追问、客户人格、澄清质量、法律推理、RAG或动态法律环境等互补评测视角 | DLawBench定义本项目的主要交互任务和官方外测；LeCoDe支持报告澄清能力，其他工作只作范围对照，不把RAG/法庭程序混入当前干预 |
| 领域知识/法律RAG | [LexRAG](https://github.com/CSHaitao/LexRAG)、[MAP-Law](https://arxiv.org/abs/2605.01486) | 关注多轮上下文下的法条检索、覆盖控制与停止 | 与本项目互补而非直接同类：本项目核心是先获取客户事实，不把法条检索增益误写成事实调查技能增益 |

## 主表为何只有四列

论文相关工作可以覆盖上述谱系，但直接主表必须回答同一可识别问题。现役四臂均使用同一冻结Qwen、客户、裁判、seed和会话协议：

1. `Base`：没有外部经验；
2. `Luna-Direct`：强教师一次性生成的静态技能，检验“强提示本身”；
3. `ExpeL-adapted`：从训练经验归纳insight，检验一般经验记忆；
4. `LegalSkillEvolve`：完整K组经验经map-reduce形成并局部演化全局playbook。

Voyager、SAGE、SkillRL、SkillX、LexRAG等不能在不改变权重、工具、动作空间或任务的情况下成为公平同构主表臂，因此应在Related Work和机制讨论中比较，而不是硬塞进同一数值表。若后续实现额外强基线，必须先冻结信息访问、推理调用和训练预算的公平合同。

## 现役设计由哪些证据支持

- **不用全失败轨迹硬造技能。** SkillLens显示经验池的成功/失败比例会影响技能质量，而且全失败池通常最差；因此K=4差异组同时提供成功和失败，tie组只提供共同失败，教师不得把tie伪造成成功。
- **不再按单案顺序整份重写。** SkillLens的并行抽取和Trace2Skill的跨轨迹归并都支持先提取局部经验、再全局合并；这对应现役map-reduce。
- **不再逐法域整份覆盖。** ACE所讨论的context collapse和增量策展、SkillOpt的有界文本编辑都支持稳定文档与局部变更；这对应精确patch和旧条款保留。
- **技能效用必须由目标模型实测。** SkillLens报告“表面合理”并不能可靠预测下游效用；因此教师只产出经验文档，最终结论来自冻结Qwen的配对轨迹和官方外测。
- **不把RAG或法条回答混作事实调查。** DLawBench区分信息收集、事实分辨和最终法律分析；本项目把F/Q与事实覆盖放在主机制层，同时保留Resolution、Fidelity和安全指标防止投机。

## 与现役方法最接近、应重点精读的代码

- [microsoft/SkillLens](https://github.com/microsoft/SkillLens)：逐轨迹mode抽取、并行归并、消费端效用评估。
- [Qwen-Applications/Trace2Skill](https://github.com/Qwen-Applications/Trace2Skill)：从多条轨迹归纳统一技能，避免trajectory-local碎片化。
- [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt)：将单份技能文档作为优化状态、用有界文本编辑演化。
- [ace-agent/ace](https://github.com/ace-agent/ace)：结构化增量策展和抗context collapse。
- [LeapLabTHU/ExpeL](https://github.com/LeapLabTHU/ExpeL)：无权重经验归纳基线。
- [SKYLENAGE-AI/DLawBench](https://github.com/SKYLENAGE-AI/DLawBench)：任务定义、四人格与七项公开指标。

## 证据状态

- `VERIFIED`：上述方法机制和项目链接已由论文主页、ACL/NeurIPS/AAAI记录、arXiv条目或官方仓库核验。
- `VERIFIED`：现役代码已经实现全局playbook、全健康K组显式记账、双map单reduce和精确局部编辑。
- `VERIFIED`：用隔离的历史真实B1 K=4证据卡完成了两次map和一次reduce诊断；16张卡全部显式记账，得到12个来源机制及8条原子playbook规则，真实Luna结构化输出、来源绑定和局部编辑合同均通过。该诊断不进入正式训练结果。
- `PENDING`：该新协议仍需全新端到端训练和冻结Qwen的实际消费端效果验证，不能提前声称指标提升。
- `PENDING`：正式论文参考文献的作者顺序、会议卷页与DOI需在落稿时逐条从出版社/会议记录导入，不以本矩阵替代BibTeX。
