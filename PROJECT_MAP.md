# 项目源码入口与归档说明

更新：2026-11-01。此文件只整理入口和职责，不迁移文件、不修改训练逻辑。

## 1. 当前主方法从这里看

当前研究任务是 OpenExempt 法定豁免推理：EC 判断每项资产适用的法条备选，
EV 为备选给出保护金额。执行器是冻结权重的 Qwen3-8B；学习对象是文本技能库。
当前完成版本为第8次完整训练、128源案件、8批，随后进行冻结技能库的新来源隔离评价。

| 层次 | 代码或配置入口 | 职责 |
|---|---|---|
| 主训练入口 | `experiments/openexempt_online.py` | 按批首答、释放训练答案、教师修订、重放准入与发布 |
| 任务与评分 | `legal_skill_guard/openexempt.py` | 数据准备、EC/EV输入与输出、原生评分及完整输出指标 |
| 技能结构与投影 | `legal_skill_guard/learning/task_scoped_skills.py` | 任务执行块、EC/EV保护、合法组合与相关技能文本 |
| 编辑与发布 | `legal_skill_guard/learning/publication.py` | 对实际父库应用差分技能编辑并校验 |
| 执行输入与标签编码 | `legal_skill_guard/learning/legal_namespace.py` | 公共法条和字面资产引用、实际技能下发；不替执行器求解答案 |
| 教师与执行传输 | `legal_skill_guard/learning/experiment.py`、`legal_skill_guard/inference/` | 实际模型/教师请求、响应和通信记录 |
| 模型阶段调度 | `legal_skill_guard/learning/phase_dispatch.py`、`ops/` | 既有单实例模型服务和运行配置 |
| 原始记录存储 | `legal_skill_guard/experiment/storage.py` | 不可变实验记录与文件落盘 |
| 正式冻结评价 | `experiments/openexempt_frozen_eval.py` | 冻结库预测、统一评分及预定同源配对比较 |
| 主方法配置 | `configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json` | 第8次实际完整运行的参数与协议 |
| 机制控制配置 | `configs/openexempt_v6_strict_policy_control_public_assets128_20261030_run01.json`、`configs/openexempt_v6_teacher_execution_withheld_public_assets128_20261030_run01.json` | 两项同版本机制控制；不是另一个主方法 |
| 新来源评价配置 | `artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json` | 十条件冻结矩阵、真实技能库绑定与预定比较 |

`*.frozen.json` 是对应运行的源码/数据/配置哈希绑定，不能将其误认为可随意删除的缓存。
已完成的 Run ID 和记录均保留，不直接复用同一ID重新运行。

## 2. 论文与结果入口

- 当前状态：`docs/CURRENT_GOAL.md`。
- 完整交付说明：`docs/reports/UTILITY_V6_PAPER_HANDOFF_20261101.md`。
- 英文投稿主稿：`paper/utility_skill_manuscript_working_20261030.md`。
- 中文独立辅助稿：`paper/sections-zh/utility_skill_manuscript_working_20261030.md`。
- 最新独立Word/PDF：`artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/`。
- 主表机器可读数据：`paper/tables/utility_frozen_results_20261101.json`。
- 图与可复核数据：`paper/figures/utility_learning_curves_20261030/`、`paper/figures/utility_method_overview_20261030/`。
- 真实运行：`runs/`，包括教师、原生回答、技能发布、失败提案、评分及完整终态。
- 根因、成本和一致性证据：`artifacts/research/openexempt_legal_scope_20261020/`。

## 3. 外部比较、历史方案与依赖

`experiments/openexempt_ace_online.py`、`experiments/openexempt_trace2skill.py`
及相应的 `legal_skill_guard/learning/` 模块是经验学习比较方法。
`openexempt_scope_control.py` 和 `openexempt_teacher_evidence_control.py`
提供当前机制控制。其余旧法律任务、ContractNLI、早期组内探索与历次主方法
保留用于解释历史实验；不把所有历史入口都当成当前主链路执行。

`data/packets/` 与 `data/cache/` 含复现数据，即使被Git忽略也不能等同于可丢弃文件。
`third_party/`、`peer-papers/` 与 `_vendor/` 保留参考实现或固定依赖材料。
`pyproject.toml`、`uv.lock` 和 `ops/inference-requirements.txt` 记录环境依赖。

本地 `.venv` 除可重建的Python环境外，还放有注册过的研究Git工作目录，
其中也有阶段调度服务使用的源码。备份时已区分它们，不能整体当缓存删除。
注册的外部临时工作目录也纳入完整恢复档案；既有分支和Git历史不清理。

## 4. GitHub备份的两层内容

目标：`H00RU/LegalSkillGuard` 的 `backup/legal-skill-evolve-20261101` 分支。
原 `main` 分支保持原样，不强推、不覆盖。

1. 可浏览层：源码、配置、现有历史跟踪文件、最新论文、关键证据与结果入口。
2. 完整恢复层：原始项目、全部现有实验记录、被忽略的数据、研究工作目录及Git对象历史。
   压缩分卷与逐文件SHA-256清单位于备份分支的 `recovery/full-project/`。
   具体完成状态、实际分卷和恢复步骤以该分支的 `recovery/README.md`、
   `archive_manifest.json` 与最终上传校验记录为准，不把“准备上传”当作“已经上传”。

不上传账户密钥、外部模型权重或可重新安装的Python依赖目录。师兄写作skills
及使用过的Nature skill另行保留；研究技能库本身仍以 `runs/` 的真实发布记录为准。
