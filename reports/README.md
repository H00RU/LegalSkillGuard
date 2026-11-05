# 研究报告与当前接续入口

## 当前方案：LSG-RR-v2（2026-11-05）

**本版替代LSG-RR-v1和旧草案。当前只推进实现与离线检查，暂不启动模型小试、thinking实测、完整建库或冻结测试。** 旧v1中“小试后自动完成Full-45训练与评测”的指令已失效；未来实验配额不构成当前执行授权。

- [完整研究方案](legalskillguard_rule_reasoning_plan_v2_20261105.md)：两项方法、明确问题、相关工作差异、实现范围与有限后续验证协议。
- [机器可读配置](legalskillguard_rule_reasoning_protocol_v2.json)：保留run_enabled=false及model_calls_enabled=false，实验步骤均关闭。
- [服务器实现阶段交接指令](legalskillguard_server_handoff_v2.md)：当前允许范围、离线验收、完成条件和可直接粘贴到新对话的指令。
- [查新与交叉审查记录](researchwrite/legalskillguard_rr_v2/README.md)：专项原文阅读、主张证据表、审查意见及闭合记录。
- [完整方案Word版](LegalSkillGuard_RR_v2_完整研究方案.docx)
- [方案、配置、交接与查新记录压缩包](LegalSkillGuard_RR_v2_完整方案与查新记录.zip)

两项方法固定为：A覆盖感知的部分规则编译；B碰撞见证驱动的技能接口细化。查新和设计审查不等同于效果验证或全球首创证明；本次发布没有产生新的实验结果。

方案保存在main；研究代码参考入口为[backup/legal-skill-evolve-20261101](https://github.com/H00RU/LegalSkillGuard/tree/backup/legal-skill-evolve-20261101)。服务器按实际版本在独立目录和开发分支接续，保护未提交修改、历史结果和运行任务。

## 已替代与历史材料

- [v1执行方案](legalskillguard_rule_reasoning_execution_plan_v1_20261105.md)、[v1配置](legalskillguard_rule_reasoning_protocol_v1.json)、[v1交接](legalskillguard_server_handoff_v1.md)：仅作历史追溯；v1配置已标记禁止执行。
- [早期下一阶段草案](multitask_rule_reasoning_next_stage_20261105.md)：已由v2替代，不再沿用其候选设计和启动指令。
- [早期两机制查新审计](novelty_audit_two_mechanisms_20261105.md)：保留其当时对象和结论，不作为v2方法的审查结论。

历史论文、代码与实验不删除，也不将旧设置结果直接作为新方法成绩。
