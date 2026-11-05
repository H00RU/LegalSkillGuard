# LSG-RR-v2 服务器交接：实现与离线检查

2026-11-05。本交接替代v1中“工程小试后自动完整训练与冻结评测”的指令。**当前只完成实现和离线检查，不启动任何研究模型实验。** 未来配额不是当前执行授权；源码中必须保留明确的关闭开关。

## 当前依据与优先级

- [v2完整方案](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_plan_v2_20261105.md)
- [v2机器配置](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_protocol_v2.json)
- [v2查新及交叉审查记录](https://github.com/H00RU/LegalSkillGuard/tree/main/reports/researchwrite/legalskillguard_rr_v2)
- [reports当前入口](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/README.md)

本次用户要求的“实现与检查，暂不正式实验”和本交接的执行开关，优先于方案中的未来实验流程。完整方案定义方法，JSON定义运行边界；旧v1、旧草案、本地旧交接或历史goal指令中与本版冲突的内容不再执行。专项查新报告是形成设计时的过程证据，若暂名或预算与主稿不一致，以v2主稿和配置为准。

## 接续现有服务器工作

先核实当前分支、commit、未提交修改、已有结果、运行进程/任务、数据缓存、依赖和资源设置，读取仓库AGENTS.md及本地docs/handoff_next_stage.md（如存在）。不输出密钥或完整凭据。

方案在main；研究代码参考入口为backup/legal-skill-evolve-20261101。该分支是参考，不保证等于服务器实际最完整版本。依据实际代码选择基线，在独立目录和开发分支接续，保留现有修改、结果和运行任务；不重置、覆盖或终止历史任务，不直接在main实施研究代码改动。

## 本次必须完成的实现

固定两项方法：A覆盖感知的部分规则编译，B碰撞见证驱动的技能接口细化。不重新广泛选题，不把经典求解或类型检查另算创新。必要的局部实现取舍可自行决定并记入决策记录；确有无法满足的核心语义约束，明确标记阻断，不能用近似实现冒充完成。

1. **共用基础。** 实现有界IR、已核共享原语、来源与版本记录、确定性执行、答案/系统状态分离、模型客户端适配、请求/token/费用账本及checkpoint。冻结模型权重；测试不使用gold、参考程序、参考proof或隐藏中间量。
2. **A。** 原文全区间登记、残余合同、非空允许补全集Ω、异答双副本查询、分离批次选择、上下文成本计数、收窄/撤销记录、固定fallback。未知作用范围不得静默删除；域外与超时不发稳定证书；有限候选池H不等于Ω。
3. **B。** 在受支持训练来源内寻找同接口异答案的碰撞；有限字段族细化、最多32个连接候选、参数化复用与冻结。每来源最多4个额外带oracle答案视图，涵盖碰撞发现、字段细化及连接消歧；未采用的已查询视图也计数。保留实体见证、聚合范围、共享额度、分配策略及顺序语义；禁止用case ID或答案指纹路由，不能凭空恢复黑盒丢失信息。
4. **数据。** 适配OpenExempt、RuleArena Airline、SARA v2 Binary、ProofWriter OWA depth5和ContractNLI。按32+4×24准备128训练来源，五库各8开发、32测试来源，分组隔离、去重、manifest和哈希可复现；不把派生视图计作新来源。用于正确性调试的材料限训练/开发或人工微例，测试标签/参考答案不进入调试、模板或接口学习。若数据无法合法取得，完成其余适配器和schema检查，单列具体缺口。
5. **后续运行入口。** 实现六臂同工具、同调用上限的路由及共享训练材料投影；不把六臂写成六次独立建库。补齐B1/B8、来源级记录、诊断、冻结哈希和复现入口，但均只做mock/dry-run。训练每来源最多两次的合并调用设计、OE双视图打包及所有失败重试计账，须能在无真实模型情况下检查。

## 离线验收和禁止事项

运行与变更相关的单元、集成和端到端mock检查；已有相关回归通过后不反复扩张测试矩阵。至少覆盖：相关未译例外阻止提前稳定；已核无关残余可以停止；空Ω、TOP、域外、冲突、超时不同处理；XOR联合批次；H与Ω分离；同实体join；逐项/整体cap；共享额度不复制；守恒但分配次序不同；开放世界Unknown；无法恢复的见证；oracle总视图上限；分区泄漏；三次预测总调用上限；重试与恢复同账；运行开关默认拒绝真实模型请求。

主数据流程可读取公开数据作去重、分组和哈希，但不开展冻结测试或人工查看测试答案修复算法。没有正式oracle的ContractNLI不制造带gold的反事实，回退不伪装成形式证明。

保持run_enabled=false、model_calls_enabled=false。**不调用研究executor/teacher，不启动20来源模型小试，不运行thinking开关的40次实测，不启动128来源8批建库，不生成B1/B8性能结果，不运行六臂开发/冻结评测，不追加种子或论文写作。** 6000/20以及256/16是未来研究请求预算，不是当前授权，也不是Codex token预算；当前研究模型请求为0。Codex自身进行代码开发与检查不计作研究executor调用。

thinking本轮只检查客户端是否正确传递开关、输出字段、截断和计费逻辑。服务端开关是否真正生效、实际成本与质量，均列为后续待实测，不用mock结果声称已经验证。

若外部信息或依赖确实阻断，只在完成不受阻部分并整理具体缺口后集中提问；常规可逆工作自主推进。技术困难或预计效果不确定，不是自行改题、扩大实验或突破关闭开关的理由。

## 完成条件与交付

交付独立分支及提交、模块到两项方法的映射、可复现离线检查命令与结果、数据准备和分区哈希记录、脱敏环境信息、预算/开关验收、已知限制与明确待办。持续更新docs/handoff_next_stage.md，并新增reports/legalskillguard_rr_v2_implementation_check_report.md。报告分开列出已实现、离线已验证、待真实模型验证，不以占位函数、只写设计或只有mock骨架冒充实现完成。

有缺失数据或核心实现阻断时如实标为部分完成。实现与离线检查全部达到上述条件后结束当前任务；即使检查通过也不自动开启实验。不创建新的对话或把任务自动转交到下一实验阶段。

## 可直接发送到服务器新对话

请接续LegalSkillGuard的LSG-RR-v2，当前任务仅完成实现与离线检查，暂不启动实验。先读取[完整方案](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_plan_v2_20261105.md)、[机器配置](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_rule_reasoning_protocol_v2.json)、[查新记录](https://github.com/H00RU/LegalSkillGuard/tree/main/reports/researchwrite/legalskillguard_rr_v2)和[本交接指令](https://github.com/H00RU/LegalSkillGuard/blob/main/reports/legalskillguard_server_handoff_v2.md)，以本版替代v1及旧草案的冲突指令。核实实际分支、未提交修改、已有结果和运行任务，读取本地docs/handoff_next_stage.md（如存在）；方案位于main，研究代码参考入口是backup/legal-skill-evolve-20261101，依据服务器实际版本在独立目录和开发分支接续，保护现有工作。两项方法固定为A覆盖感知的部分规则编译、B碰撞见证驱动的技能接口细化；自主完成共用IR与执行后端、两方法、五库适配与去重划分、独立oracle/评分核验、预算账本、冻结与恢复、六臂路由及相关单元/集成/mock端到端检查，不重新选题。保持run_enabled=false及model_calls_enabled=false：不调用研究executor/teacher，不跑模型小试、thinking实测、完整建库或冻结测试；方案中的配额与预算仅供后续阶段。不得用测试标签调试，也不把模拟检查当成模型效果。持续更新交接文件和实现检查报告，交付代码提交、复现命令、检查结果、数据/配置哈希、已知限制及待实测项；全部完成后结束本任务，不自动进入实验或论文写作。常规可逆工作自主推进，只就无法自行核实的必要信息或真实资源缺口集中提问，不反复确认。
