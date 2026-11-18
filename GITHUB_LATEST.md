# 当前研究分支交付

五库 B8 冻结评估已结算，原定 128 个训练来源、八批训练、五个 DEV 检查点、独立消融、PARSE 强对照及静态 B0 参照均有证据。M1 的 Diversity balanced accuracy 差值为 +12.50 个百分点，95% 配对区间 [−5.00, 30.00]。M2 的两组原生预测逐项相同。两项方法分别取得可靠独立增益的研究目标尚未达成。

[论文初稿](reports/legal_skill_convergence_20261117/paper/METHODS_AND_DEVELOPMENT_RESULTS.md) · [原生计分](reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_NATIVE_TABLES.md) · [覆盖率](reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_COVERAGE.md) · [证据封印索引](reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_EVIDENCE_MANIFEST.json) · [项目交接](docs/NEW_CHAT_HANDOFF.md)

---

当前项目全部核心代码已同步并独立核验（2026-11-17）：
https://github.com/H00RU/LegalSkillGuard/tree/354bece66fd9a0b1e7bc8dab1a6d7159ee141345

完整核心文件清单：
https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/docs/CORE_CODE_MANIFEST_20261117.json

研究分支：research/paired-interface-structural-transfer-20261116。清单1613文件全部匹配；本次新增/更新172文件，58/58配对接口模块齐全，包含正式工作流和M2修订。原始科学源码未改动；177参考、累计账本12427/reserved0及旧证据保留，本轮新增研究调用0。main未修改，未启动训练/测试，Goal未完成。以下保留先前发布记录。

M1最新可行性与停止结论（已上传并逐文件核验）：
https://github.com/H00RU/LegalSkillGuard/blob/1f132108fa326d46118c3c708458fbbafec7bfb2/reports/two_method_followthrough_20261116/M1_FEASIBILITY_DECISION_20261117.md

源码、依赖与首批复现包：
https://github.com/H00RU/LegalSkillGuard/blob/1f132108fa326d46118c3c708458fbbafec7bfb2/reports/two_method_followthrough_20261116/M1_evidence_20261117/README.md

有限真实验证补充包（18旧响应+2新增响应、选择/评分/归因）：
https://github.com/H00RU/LegalSkillGuard/blob/1f132108fa326d46118c3c708458fbbafec7bfb2/reports/two_method_followthrough_20261116/M1_finite_evidence_20261117/README.md

新增2调用/5576 tokens；M1原生F1=1/3但完整正确0/4，正分依赖既有源审unknown→true。当前M1版本与M2均停止扩展；177参考、原始分数、连续账本12427/在途0与曝光事实保留，整Goal未完成。以下为历史发布记录。

# 最新发布：M2两关结论与M1当前情况，2026-11-17

[M2两关计算与停止结论](https://github.com/H00RU/LegalSkillGuard/blob/b9795546d5356abb9a02280cd39290442a9b30f9/reports/two_method_followthrough_20261116/M2_TWO_GATE_DECISION_20261117.md) · [M1当前情况](https://github.com/H00RU/LegalSkillGuard/blob/b9795546d5356abb9a02280cd39290442a9b30f9/reports/two_method_followthrough_20261116/M1_STATUS_20261117.md)

用户明确要求的两份说明已上传，提交 `b9795546d5356abb9a02280cd39290442a9b30f9`；已用GitHub提交接口、固定提交原文及远端refs独立核对，逐字节一致，变更路径恰为两份Markdown。main与原证据分支保持。原始数据、账本、修订代码及私有本地祖先未上传。研究Goal保持blocked、未完成；发布没有恢复研究执行。

---

# 已发布：当前 Goal 状态说明，2026-11-17

[固定提交文档](https://github.com/H00RU/LegalSkillGuard/blob/84c8dd5f774276f7b883c6938e778e1d8eed0584/reports/two_method_followthrough_20261116/GOAL_STATUS_20261117.md) · [纯文本](https://raw.githubusercontent.com/H00RU/LegalSkillGuard/84c8dd5f774276f7b883c6938e778e1d8eed0584/reports/two_method_followthrough_20261116/GOAL_STATUS_20261117.md)

按用户最新范围，本次远端只新增一份状态说明，已独立回读并逐字节校验。main与原公开证据分支保持不变。此前225文件及证据包方案已被“仅说明文档”的指令取代，未上传；相关本地准备材料继续保留。研究Goal仍blocked、未完成，正式矩阵未启动。

---

以下为此前本地准备与历史导航，不代表已全部上传。

# 当前发布：两方法 Goal 受阻，2026-11-17

[阻断说明与实际进度](reports/two_method_followthrough_20261116/BLOCKED_STATUS_20261117.md) · [可离线复核的证据包](reports/two_method_followthrough_20261116/blocked_evidence_20261117/README.md) · [完整下载包](reports/two_method_followthrough_20261116/blocked_evidence_20261117.zip) · [M2反证](reports/two_method_followthrough_20261116/M2_IDENTIFIABILITY_AUDIT.md)

当前 Goal 为 blocked、未完成。主 M2 的 unrestricted 选择退化与独立测试库存缺口均已核实；正式矩阵未启动。177 个域内参考视图及全部原始资产保留，旧 Goal／候选／执行队列不恢复。下文是此前交接历史，当前状态以上述阻断说明为准。

---

# 最新交接：旧Goal已清除，准备新对话

2026-11-16。旧Goal已由用户clear，当前无active Goal、无研究执行队列。

[新对话交接](docs/NEW_CHAT_HANDOFF.md) · [项目入口](PROJECT_MAP.md) · [当前状态](docs/CURRENT_GOAL.md) · [历史证据索引](docs/METHOD_REDESIGN_CURRENT.md)。

[旧Goal精炼总结](reports/legal_skill_evolution_run_20261111/component_training_20261115/GOAL_RETROSPECTIVE_20261116.md)记录参考工作、候选选择、实现困难、强对照和否定结果。它是研究资产，不是继续旧方案的指令。

原始数据、代码、结果、连续账本和未提交工作保留；main不修改。新任务、方法和实验计划由新对话确定。本次交接不调用研究模型或启动实验。
