# 评估与准入合同

> 与2026-09-26现役单一playbook和共享opening-only议程协议配套。

## Playbook准入

一个新版本进入工作库前必须同时满足：

1. 严格符合结构化技能schema，稳定ID为`general.legal_fact_elicitation_playbook`；
2. 只由精确`ADD/REPLACE/DELETE`操作产生（首次创建0—8个、已有版本每批0—2个），未命中条款逐字保留；
3. 每个非空操作引用至少一个map阶段真实机制的group ID；对应K=4轨迹、评分和证据卡哈希可重放；
4. 累计provenance等于父版本来源并集加本轮实际使用来源；
5. 不含案件ID、专名、隐藏事实、官方答案、固定轮数、确定法律结论或胜诉承诺；
6. 不创建触发器、目标改写器、强制停止器或第二决策模型；
7. 完整运行时提示不超容量。

这些是可信与安全硬门，不是效果门。下一块配对结果不会拒收或回滚已发布版本；可定位的退化可在后一轮用DELETE/REPLACE修订。证据不足时教师应NOOP，程序不得代写经验。若同类低效行为和警告持续出现，现有条款在纸面上覆盖该主题并不能证明它可执行；教师可在来源证据支持下REPLACE为更明确的条件—动作规则。

## 训练信号

每张健康证据卡包含同案K=4全部轨迹。`process_differentiated`组可支持成功和失败机制；`process_tied`组只能支持共同失败。证据卡同时携带终止状态、真实客户回应类型、事实增量、行为警告以及每回合行动前仍未解决的可见目标。每个map还接收该批轨迹实际使用的精确父playbook（首批为null），使教师能区分“纸面已有规则”和“律师实际执行了规则”；父文档变化必须改变map输入绑定哈希，旧artifact不得跨父版本复用。两个map包必须完整且不重叠覆盖本批所有健康组，reduce只能引用map中已出现的来源。

教师规则必须具备三项质量：具体失败机制、可执行纠正动作、明确高风险动作黑名单。每个map包还必须把未形成新机制的group ID显式列出，不能静默忽略低差异或难例。仅复述冻结提示中的“不要重复、一次一个问题、优先重要事实”不构成新技能。

## 前瞻开发指标

每个playbook新版本在下一未见块相对精确父版本做同案配对：

- 主指标：`unique_disclosed_facts_per_question`，越高越好；
- 完整性：`unique_disclosed_facts`、`fact_coverage`、`critical_fact_recall`；
- 成本：`question_turns`、`repeated_question_rate`；
- DLawBench兼容：elicitation、resolution、fidelity、identified evidence gaps；
- 安全：premature final、unsupported claim、belief-as-fact、hidden leak；
- 运行：policy/client fallback与结构修复率。

报告均值、逐案差值、案件聚类bootstrap 95%区间和实际问题/回应过程。开发点用于训练曲线与下一轮编辑诊断，不作版本选择。跨批原始均值可描述但不是同案因果估计。

运行机制只报告执行器记录的完整提示文档暴露：会话实际收到的playbook ID、提示哈希、覆盖案件数和覆盖率。现役策略没有运行时技能选择动作，因此不从固定为空的`activated_skill_ids`推导“激活率”，也不把模型不可观测的内部采纳冒充机制指标。

精确重复、`unavailable`重问、复合问题和向客户索要法律判断不设独立终止端点。只要动作在结构、目标身份、隐私与泄漏边界上可执行，就必须实际调用客户；其实际回应、零增量、重复与提问成本按普通轨迹计量，不能通过隐藏修正或少算一次提问伪装F/Q改善。只有律师自主`final`/`abstain`或应急horizon能结束会话。后者是安全上限下真实、可评分的策略失败：保留全部问答与指标并进入教师证据，不作健康成功，也不作执行完整性故障排除或重采样。

## 最终外测

最终库冻结后，在官方CN30上同一控制器运行Base、Luna-Direct、ExpeL-adapted、LegalSkillEvolve四臂，共享Qwen、opening-only议程、客户、裁判、seed、预算和会话协议。主表以F/Q为主终点，同时报告事实覆盖、新事实数、提问数、重复、过早结束、安全和DLawBench兼容指标；次要指标作Benjamini-Hochberg校正并报告配对效应量与95%区间。

CN30不参与训练、教师、局部编辑或阈值选择。因历史上看过方法级聚合结果，最终实验表述为benchmark-aware锁定复评，不冒充首次私有盲测。
