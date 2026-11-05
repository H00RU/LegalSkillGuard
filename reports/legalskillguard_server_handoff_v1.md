# 服务器 Codex 第一阶段 goal 接续指令

版本：LSG-RR-v1，2026-11-05。以下文件是当前执行依据，替代[旧草案](multitask_rule_reasoning_next_stage_20261105.md)中的候选设计和交接指令；旧文件保留历史记录。模型权重冻结，“训练”指外部技能建库。

- [完整方案](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_execution_plan_v1_20261105.md)
- [机器配置](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_protocol_v1.json)
- [本交接指令](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_server_handoff_v1.md)

**本次 goal 仅推进第一阶段。** 第二阶段完整对照、额外种子及论文写作不自动启动。以下第一阶段范围优先于完整方案中面向全研究的继续推进描述。启动时确认该目标已登记为当前 goal，不能只口头宣称开启。若当前 Codex 版本不支持 Goals，明确报告缺少的功能，不伪称已激活。

请接续 LegalSkillGuard 的规则约束推理研究，按 `reports/legalskillguard_rule_reasoning_execution_plan_v1_20261105.md` 与 `reports/legalskillguard_rule_reasoning_protocol_v1.json` 执行；旧候选方案与其冲突时以这两份为准。先读取 `docs/handoff_next_stage.md`（如存在），核实实际分支、未提交修改、已有结果、运行任务、模型/数据缓存和资源授权。已知研究代码参考入口是 `backup/legal-skill-evolve-20261101`，审阅快照为 `aac4e3dde407fe64dfe67f6b96354b49b44fb3be`；保护服务器实际工作，在独立目录/开发分支接续，禁止重置或终止已有实验。

本轮方向已经锁定：A规则干预见证约束结构修复，B可信语义见证下的非补偿更新，C冻结技能的规则变化迁移评测资源；不要再广泛搜寻候选创新、临时增加第三个算法或更换研究方向。实现原文中的具体算法和强简单对照，不以概念名称代替实现。来源配额固定为OpenExempt 32、其余四库各24训练，总计128；每库8开发、32冻结测试。SARA采用同题干/同事实文本传递合并且测试优先去重；OpenExempt主测EC/EV分列，规则变化诊断只用EV。保留ContractNLI自然语言覆盖组，不能假装所有题目都能形式验证。

先完成适配器、oracle独立性、分区隔离、字段泄漏、预算账本和无模型契约检查；在训练来源上进行一次有上限的小试，核验thinking真实开关、输出截断、token/时延与费用。小试通过标准是协议与实现正确，不是显著涨分；最多进行一次针对明确实现错误的修复。随后务必完成一次Full-45的完整128来源、8批建库并冻结B1/B8，再打开测试，交付五库各自结果、规则变化覆盖/结果、空库对照、B1结果、真实费用和复现实验命令；不要只完成小试就停下等待是否要完整训练。

第一阶段executor硬上限6000、teacher20；单次完整建库executor4000、teacher16，重试和恢复不重置账本。这些是实验模型的物理调用上限，不是给Codex goal设置的token预算。完整研究的18次建库和85000/301总额仅是后续矩阵，不属于本次goal的自动执行范围。不因结果不好追加数据、模型、种子或方法，也不挑最好结果。第一阶段交付并核验后完成当前goal，等待下一阶段明确指令；若缺少或超出真实资源授权，先完成可逆准备、给出实测成本和剩余任务，只集中询问资源缺口，不能把调用上限当作新增付费授权。

持续更新 `docs/handoff_next_stage.md`、来源manifest、逐run台账及决策记录。所有实验结果保留来源级预测、库版本、配置hash、物理调用和缓存计数。到达预算上限则保存状态并明确未完成，不伪称已跑完；只有可定位实现/协议bug允许重跑受影响项，且仍计预算。若某组件没有独立收益，按既定判据收缩论文主张，完成本研究，不重新选题。常规可逆工作自主推进；只就无法从仓库/服务器核实的必要信息或超出现有授权的资源集中提问。

本交接不要求创建或更改任何其他对话，也不预设服务器已经配置好数据与模型。你应依据本地实况执行并记录差异。

## 可以直接粘贴到服务器 Codex 新对话的指令

/goal 接续并完成 LegalSkillGuard 的 LSG-RR-v1 第一阶段。先读取[完整方案](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_execution_plan_v1_20261105.md)、[机器配置](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_protocol_v1.json)和[交接指令](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_server_handoff_v1.md)，以这版替代旧候选方案，并确认目标已登记为当前goal。核实服务器实际分支、未提交修改、已有结果、运行任务及本地docs/handoff_next_stage.md；方案位于main，研究代码参考入口是backup/legal-skill-evolve-20261101，依据实际工作版本在独立目录/分支接续，保护现有修改与实验。三项研究设计已经锁定，不再重开选题。自主完成数据去重与划分、独立oracle和评分核验、泄漏与预算检查，按协议核实thinking真实开关及成本，完成有限小试后继续一次Full-45的128来源、8批完整建库；小试无需显著涨分，不得停在小试。冻结B8后再评估，交付五基准各32测试来源的结果、空库对照、B1原始评测、规则变化覆盖与结果，以及来源级预测、冻结库、配置/数据hash、调用费用、复现命令和第一阶段结论。第一阶段executor≤6000、teacher≤20，单次完整建库≤4000/16，重试与恢复均计入原账；这些是实验请求上限，不是Codex的token预算，也不新增付费授权。仅就缺少必要信息或超出既有资源授权集中询问，其他可逆工作持续自主推进并更新项目交接与台账。不为涨分追加任务、种子或改测试；预算耗尽时保存状态并如实说明未完成。只有上述交付实际完成并核验后才标记goal完成；本次不自动进入第二阶段对照矩阵或论文写作。

`/goal <目标>` 是支持 Goals 的 Codex 的启动入口，参见[官方说明](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)。本文件只提供启动指令，未代替用户在服务器新对话执行。
