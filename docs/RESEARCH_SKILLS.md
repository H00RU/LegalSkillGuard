# 研究技能与本次接手

2026-11-16。最终工作目标是形成论文；本次任务完成项目接手和研究技能安装，未创建新 Goal、选择新候选或启动实验。唯一项目目录仍是 `/home/yndx/hhy/legal-skill-current`，开发分支仍是 `repair/lift-corev-activation-20261112`。

## 接手后的研究认识

项目已有的研究对象是：从法律原文与合法反馈学习版本化的外部可执行技能，在后续案件中复用。历史实现涵盖程序与规则获取、法源绑定、案件观察与转换、原生执行、更新和回归保护；历史研究没有更新模型权重。相关代码、冻结库、数据清单、原始响应、失败和结果均保留为可复用资产。

旧固定研究 Full 的 TEST 宏平均为 53.848%，AllPorts＋CoRev 为 42.619%，整体提升是真实历史结果；专门 Lift 学习和共同修订模式没有发生，不能由分差归因其机制。后续 C＋观察契约完整 DEV 为 46.884%，NoC/空库为 48.134%；最近 C 的原 TRAIN 为 76/96，充分修复的普通教师为 75/96。旧 Goal 未验证两项独立贡献，已经 clear。后续方法和论文主张依据新任务与新证据确定，旧候选、批次及未派发任务不转为执行队列。

旧 TRAIN、DEV 和 TEST 暴露记录全部保留；旧 TEST 不能作为新的盲测。唯一连续账本是 `artifacts/rr_v2_preflight/research_ledger.sqlite3`，本次核对为 executor 11741、teacher 329，共 12070 条，reserved 0。交接时已有 1402 份科学文件、76 份未提交或未跟踪文件、冻结 README 及账本文件均通过原保护清单的哈希核对。

事实来源：[当前状态](CURRENT_GOAL.md)、[交接](NEW_CHAT_HANDOFF.md)、[资产索引](METHOD_REDESIGN_CURRENT.md)、[旧 Goal 回顾](../reports/legal_skill_evolution_run_20261111/component_training_20261115/GOAL_RETROSPECTIVE_20261116.md)。这些数值是已有研究的记录，不是新实验结果。

## 已有的师兄技能与写作技能

现有技能位于 `/home/yndx/.codex/skills/`，本次保留原文件。

|用途|技能|
|---|---|
|选题和贡献|`paper-ideation`|
|全文组织|`paper-writing`|
|题目、摘要和引言|`paper-abstract-intro`|
|相关工作、方法和公式|`paper-related-method`|
|实验、结论和附录|`paper-experiments-appendix`|
|图表和数据核查|`paper-figures-data`|
|排版和投稿|`paper-layout-submission`|
|中文与英文反防御性写作|`anti-defensive-writing`、`anti-defensive-writing-en`|
|精炼科学表达|`nature-paper`|

## 新增 Supervisor-Skills

来源：[HKUSTDial/Supervisor-Skills](https://github.com/HKUSTDial/Supervisor-Skills)，香港科技大学（广州）DIAL。固定提交：`4bd3fef393e5ffc891c74309a5ef6c5ad3ad12c8`。12 个技能分别安装到 `/home/yndx/.codex/skills/<技能名>/`，保留各技能自己的 `references/`、脚本与其他随附文件。

|用途|技能|
|---|---|
|候选 idea 评估|`idea-evaluator`|
|文献调研|`deep-research`|
|研究流程指导|`vibe-research-workflow`|
|技术论文结构|`tech-paper-template`|
|Benchmark 论文结构|`benchmark-paper-template`|
|引言起草|`intro-drafter`|
|有证据支持的正文起草|`paper-writer`|
|语言润色|`paper-polish`|
|图表设计|`figure-designer`|
|参考图重建为 Draw.io|`drawio-reconstruction`|
|投稿前审查|`pre-submission-reviewer`|
|Rebuttal|`rebuttal-guidance`|

整仓压缩包下载未完成，且中止前没有安装技能；随后仅下载固定提交下的技能文件，逐文件验证 Git blob 哈希，使用官方 `skill-installer` 的校验及复制流程安装。未执行上游随附脚本，也未安装其可选运行依赖。完整上游 README、LICENSE、CHANGELOG 和安装回执保存在 `/home/yndx/.codex/skills/.supervisor-skills/`；项目内副本见[安装回执](history/handoff_skills_20261116/supervisor_installation.json)。仓库根许可证为 CC BY-NC-SA 4.0，各技能保留原许可声明。

## 后续使用方式

按当前任务选择相关技能，并在实际使用前完整读取相应 `SKILL.md` 及所需引用。选题可用师兄 `paper-ideation` 产生方向，再按需要调用 `deep-research` 和 `idea-evaluator`；论文各节使用师兄对应技能，Supervisor-Skills 提供额外的结构、证据或审查视角。中文与英文写作分别结合对应的反防御性写作技能。

用户当前指令和项目事实边界优先。技能中的模板、评分、角色或推荐动作不自动形成新 Goal、模型调用权限或执行队列。写作组织可以突出已获支持的贡献，但数值、比较条件、数据暴露、失败和不确定性必须准确。作者工作流技能与项目学习得到的法律技能库分属不同用途；本次安装不修改律师、教师或执行器提示词。

后续对话轮次可发现新安装技能；需要调用时也可通过上述绝对路径读取。Draw.io 等技能的具体工具依赖在实际任务需要时再核对。

本次接手与保护检查见[核对回执](history/handoff_skills_20261116/verification.json)。该记录只确认接手和安装，不评价新研究创新性，也不恢复旧研究。
