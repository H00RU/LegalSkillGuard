# 研究报告与当前执行入口

## 当前方案：LSG-RR-v1（2026-11-05）

规则约束推理下一阶段以以下三份文件为准：

- [完整定稿执行方案](legalskillguard_rule_reasoning_execution_plan_v1_20261105.md)：三项贡献、近邻差异、具体实现、数据划分、对照与停止条件。
- [机器可读配置](legalskillguard_rule_reasoning_protocol_v1.json)：128训练来源、五基准各32测试来源、阶段预算与执行范围。
- [服务器 Codex 第一阶段 goal 交接指令](legalskillguard_server_handoff_v1.md)：含可直接粘贴的新对话启动指令及完整链接。

**本次启动范围只有第一阶段：预检、小试、一次 Full-45 完整建库与冻结评测。** 后续完整对照矩阵和论文写作保留为计划，不自动启动。第一阶段不是只跑小试，也不以必须涨分作为结束标准。

方案保存在 `main`；EC/EV研究代码入口仍为 [`backup/legal-skill-evolve-20261101`](https://github.com/H00RU/LegalSkillGuard/tree/backup/legal-skill-evolve-20261101)。服务器应保护实际工作分支、未提交修改、已有结果和运行任务，再独立接续。

## 已替代/历史材料

- [旧下一阶段草案](multitask_rule_reasoning_next_stage_20261105.md)：已由 LSG-RR-v1 替代；正文保留用于追溯，不再执行其中的候选设计。
- [旧两项候选机制审计](novelty_audit_two_mechanisms_20261105.md)：保留查新证据，其旧候选结论不替代当前三项设计。

其他报告及旧论文结果保留各自的历史上下文，不与新协议成绩混用。
