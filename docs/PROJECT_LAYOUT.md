# 项目目录与工作入口

整理日期：2026-10-15。只整理入口和说明，不改变方法、数据划分、评分或运行中的冻结文件。

## 当前项目

- 日常入口：`/home/yndx/hhy/legal-skill-current`，软链接到下述实际目录。
- 实际目录：`/media/sangfor/vdb/legal-skill-evolve`，唯一当前源码，不另复制一套到 home。
- `legal_skill_guard/`：律师推理、技能学习、查询执行、评分及实验核心代码。
- `configs/`：配置与对应冻结清单；不是所有保留配置都已启动。
- `runs/<Run ID>/`：各次实验的冻结输入、运行时源码快照、实际模型输出、技能版本与进度。
- `reports/experiments/`：预先确定的协议及已完成部分的审计说明；失败试验也保留。
- `docs/`：方法、历史决策、重建边界及当前研究目标。
- `data/`、`artifacts/`：数据与可追溯工件；不是临时清理目录。
- `third_party/`：实际采用的上游实现及许可证；`tests/` 是小规模边界测试。

## 当前后台工作

当前主方法开发入口为`configs/contractnli_review.json`，协议见[答案复核技能](ANSWER_REVIEW_METHOD.md)。
新Run `legal_contractnli_answer_review_learning_20261015_run01`：4批×2案、8后续来源，
56次新律师、4次新教师；启动与完成状态以其`progress.json`和实际工件为准。
旧三条件/多条件有限试验**不是已经完成的正式论文比较**。
上述run启动时按用户要求在普通对话中实施，未开Goal。
15:09用户明确要求新建Goal，现为active；最新目标与执行顺序见[CURRENT_GOAL](CURRENT_GOAL.md)。

| Run ID | 用途 | 查看进度 |
| --- | --- | --- |
| `legal_contractnli_feedback_completion_20261015_run01` | 已完成124个全链物理律师调用、14教师响应及四来源探针，未建立稳定优势 | `completion.json`及独立八来源`main_completion.json`，进程已退出 |
| `legal_contractnli_adaptive_memory_comparison_20261015_run01` | Schema拒绝后失败，2新律师/0教师响应/1请求尝试；工件保留 | `failure.json`，不是仍在等待或方法效果失败 |
| `legal_contractnli_adaptive_memory_comparison_20261015_run02` | 13:47完成58新律师/16教师/2共享冷答；没有整体胜过强空库 | `completion.json`与`results.md`；失败费用见`restart_provenance.json` |
| `legal_contractnli_answer_review_learning_20261015_run01` | 当前主方法四批已完成，正在完成后续8来源三条件评价 | `progress.json`，尚无完整新案结果时不下结论 |
| `legal_contractnli_answer_review_anchor_diagnostic_20261015_run01` | 主run完成后接续固定4个已见TRAIN来源的初答依据干预，10新律师/0教师 | `progress.json`，是合成输入诊断，不是训练或论文主成绩 |

旧 `legal_contractnli_grounded_feedback_learning_20261015_run01` 于10:11在B4强制教师审计引用检查处失败，
44个律师回答和7个教师输出保留。旧 `grounded_references` 随父失败停止，已完成5个教师发布但0律师回答；
旧 `literal_receipt_delivery` 因依赖失败停止、0新调用。这三者都不冒充仍在训练。
新分叉不改写这些失败记录，继承真实检查点与独立有效参考库，去掉B4强制coverage自报并重新调用教师。
它使用明确修订过的开发协议，不是从头同一预注册干预，也不是独立学习重复。

后台进程不依赖对话持续采样。实时状态以进度、真实模型工件和完成/失败记录共同核对，
不能把本说明中的阶段描述当成完成证据。不要重复运行这些 worker。

`configs/contractnli_main.json` 是另外保留的 388 次律师调用完整比较配置，
尚未启动；它已经不是默认CLI入口，不应与当前方法混用。

## 历史恢复材料与备份

| 位置 | 身份 |
| --- | --- |
| `/home/yndx/hhy/legal-skill-archive` → `/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln` | 恢复档案总入口，含旧 Git 镜像、幸存临时源码、对话修改回执及重建证据 |
| `/home/yndx/legal-skill-recovery-20261015.8k6bZM` | 文件丢失后首先建立的约 699 MB 原始保全目录，不是新项目 |
| 上述归档目录内同名 `legal-skill-recovery-20261015.8k6bZM/` | 原始保全件的副本；本次整理用 `diff -qr` 核对目录树及全部文件内容一致 |
| `/home/yndx/hhy/legal-skill-backups` → `/media/sangfor/vdb/legal-skill-backups` | 已校验的源码 bundle、配置与实际实验工件备份 |
| `/media/sangfor/vdb/legal-skill-runtime` | 新项目的 Python 运行时，不是另一套业务源码 |
| `/home/yndx/hhy/legal-skill-evolve` | 旧项目幸存残留；旧模型服务参数仍引用它，不搬动、不当作当前工作树 |
| `/home/yndx/hhy/归档/` | 本轮已逐份比较的旧版六主题技能；12:36核查路径已不存在，本助手未删除，当前运行不依赖它 |
| `/home/yndx/hhy/paper-skills/` | 当前七主题论文技能，覆盖上述六主题并增加找idea；两版不是逐字相同 |

恢复目录中的 `README.md` 记录的是当时的取证状态，早期 `reconstructed_source_v2/v3`
也只是恢复过程产物，不代表当前代码版本。归档中的旧聊天记录和聚合指标不能替代已丢失的原始模型回执。

本次没有删除任何恢复材料，没有覆盖原始取证文档，也没有移动实际项目、模型路径、
冻结源码、原生输出或教师记录。软链接只是统一访问入口，不增加源码副本。
vdb 上的多个目录不等于已具备异机/离线备份。
