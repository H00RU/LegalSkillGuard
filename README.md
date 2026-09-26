# LegalSkillEvolve

LegalSkillEvolve研究冻结Qwen3-8B能否从同案K=4法律咨询轨迹的组相对经验中持续改进一份紧凑、结构化的事实调查playbook，使模型随128案顺序经验以更少提问获得更多关键客户事实。下一未见块用精确父库影子测量上一版playbook的行为增量，但不把单块结果用作版本拒收门。项目不微调模型权重，不用硬编码动作替代律师决策。

项目发行名和论文方法名均为`LegalSkillEvolve`。Python导入命名空间暂保留`legal_skill_guard`，仅为兼容既有不可变run工件，不表示仍采用旧Guard研究协议。

现役协议修订于2026-09-26：128案冻结为8块×16案，训练统一使用合作型P_WD。每个归因健康案件的K=4全部压缩为一张可审计证据卡：有组内差异时保留真实相对优劣，无差异时保留共同失败面并标记tie；若任一路使用系统fallback或破坏归因，则在奖励与教师结果产生前整组隔离并显式记账。第1—7块中，16张卡固定分给两个互不重叠的Luna map调用；每个map同时看到这些轨迹实际使用的精确父playbook，以区分新机制和“纸面已有但仍未执行”的缺陷，并抽取来源绑定的成功/失败机制，再由一个reduce调用跨案件合并、去重。首次创建全局playbook时允许最多8个精确ADD/REPLACE/DELETE操作，以后每批最多2个局部操作；未命中的旧条款逐字保留。若纸面已有规则仍伴随同类行为失败，教师可把它改成更可执行的条件—动作规则；只有行为证据支持且不能由现有条款执行的新机制才新增，避免名义逐条编辑、实质整份重写。

教师事务是原子的：两份map工件必须完整覆盖且不重复覆盖本批全部健康K组，reduce中的每个操作必须引用map阶段真实提取过的group ID。每个操作只承载一条可独立替换的规则，禁止把编号清单或多条独立指令塞进一个条款。目标条款必须逐字存在，系统只执行声明的局部编辑；错配、越界、重复编辑或容量溢出会失败关闭，不允许系统补写经验或整份自由改写。

上一版playbook在下一未见块自然暴露，并用同案、同seed、同sample的精确父版本影子作前瞻测量。下一轮教师读取真实问题、客户回应类型、事实增量、行为警告、终止状态和精确字段变化，用局部DELETE/REPLACE纠正可定位退化或ADD新机制；不把未来块或官方外测反馈给教师。

每案先由同一冻结Qwen仅凭公开opening生成一次共享的opening-only事实议程；同案K=4和所有比较臂复用同一结果。模型只能选择开场中的逐字连续主题短语和一个闭集事实属性，Python据此确定性生成目标，不能自由补写开场外主体、事件、法律概念或数值。议程不看技能、人格、隐藏事实或评分，不规定问题顺序、最低提问轮数或下一动作，只把开场支持且尚未知的客户可回答维度写入可见状态；合法空议程也不会封闭`new_visible_gap`。逐轮律师看到公开开场、此前完整的律师问题与客户回答、紧凑状态账本以及本臂playbook，仍自主选择议程目标、提出新维度或结束。正式入口没有技能条件计划器、技能触发器、检索器或独立动作改写模型；第8块不生成无法后续观察的新版本，冻结后的官方CN30四臂评测回答最终整体效用。

技能运行形态是“单一全局playbook直接注入”：同一紧凑文档与在线状态进入每轮唯一的完整动作决策。教师写入的`procedure`、`question_guidance`、`contraindications`和`failure_modes`保持逐字不变，运行时不再套用旧触发卡的`additional_question_budget`、`exclude_when`等控制元数据。Qwen自主选择实际动作；程序不要求它自报采用了哪条规则，也不把文档编译成触发规则、目标选择器、停止器或动作改写器。

客户调用前，只有结构、目标身份、隐私边界等会使动作不可安全执行的错误，才会反馈给同一冻结Qwen作有界重采样，系统不替它编写问题。精确重复、重问已标记`unavailable`的目标、复合提问或请客户作法律判断是可评分的律师行为：均真实送达客户，计入提问数、重复率、收益和教师证据，不被隐藏改写或拦截。会话只由律师自主`final`/`abstain`或不向模型暴露的应急horizon结束。命中horizon是安全上限下真实、可评分的策略失败：不算健康成功，但保留进入教师证据，不作执行完整性故障排除。K=4承担探索，Ours内部不强制无技能分支。主终点是`unique_disclosed_facts_per_question`，并配套报告事实覆盖、新事实数、提问数、playbook暴露率、重复追问、过早结束、unsupported主张和DLawBench兼容指标。

## 现役执行真源

- docs/architecture/current_research_protocol.md：研究问题、数据流、直接累计与前瞻诊断的主张边界。
- docs/architecture/evaluation_contract.md：来源硬门、主指标、配套指标和统计合同。
- docs/architecture/artifact_naming.md：不可变工件及退役命名。
- docs/architecture/llm_role_decisions.md：Qwen、gpt-oss-20b、Luna与确定性代码的边界。
- docs/research/related_work_matrix.md：相关工作分层、直接基线边界与现役机制的文献依据。
- docs/operations/main_experiment_execution.md：fresh/resume、监控、停止与结果出口。
- configs/experiments/main_experiment.yaml、configs/data/main_training_batches.yaml、configs/models/roles.yaml：机器可执行真源。

## 方法边界

- 训练run自身的两臂报告只作机制诊断；其空库与全局playbook臂都使用确定性的`general`上下文，不运行技能领域路由。论文主表必须在最终库冻结后，由同一控制器重跑Base、Luna-Direct、ExpeL-adapted和LegalSkillEvolve；主表为支持多领域基线而共享的方法无关固定领域路由不属于Ours干预。
- 官方CN30使用同一冻结Qwen、客户、裁判、seed、预算和opening-only固定法域路由。它不进入训练、教师、技能生成或阈值选择。
- CN30已有框架级聚合诊断历史，因此最终结果表述为benchmark-aware锁定复评，不冒充此前从未访问的私有确认性测试。
- 下一块精确父版本比较衡量整份playbook更新的联合增量，不能倒签其中某条规则永久有效。逐轮可审计对象是文档暴露、提示哈希和实际动作；不虚构模型内部究竟采用了哪一条规则。规则级因果效应需要另行预声明消融。

## 快速检查

    .venv/bin/python scripts/audit_paper_protocol.py
    .venv/bin/python scripts/audit_training_batches.py
    .venv/bin/pytest -q

正式运行见docs/operations/main_experiment_execution.md。协议或代码改变后必须使用新run ID和空初始库；旧暂存拒收run、旧轨迹、旧入口和旧检查点只能作为隔离历史，不能resume或计入现行结果。
