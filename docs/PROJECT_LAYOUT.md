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

以下是整理时正在执行的有限开发试验，**不是已经完成的正式论文比较**。

| Run ID | 用途 | 查看进度 |
| --- | --- | --- |
| `legal_contractnli_grounded_feedback_learning_20261015_run01` | 标准反馈与逐条证据反馈的技能学习、训练/保留/后续来源比较 | 对应 `runs/<Run ID>/progress.json` |
| `legal_contractnli_grounded_references_20261015_run01` | 固定技能与仅来源标签学习对照；等待前一试验完成后执行后续来源回答 | 对应 `runs/<Run ID>/progress.json` |

后台进程不依赖对话持续采样。实时状态以进度、真实模型工件和完成/失败记录共同核对，
不能把本说明中的阶段描述当成完成证据。不要重复运行这些 worker。

`configs/contractnli_main.json` 是另外保留的 388 次律师调用完整比较配置，
整理时尚未启动；默认 CLI 的 `launch` 对应它，不是以上两个后台试验。

## 历史恢复材料与备份

| 位置 | 身份 |
| --- | --- |
| `/home/yndx/hhy/legal-skill-archive` → `/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln` | 恢复档案总入口，含旧 Git 镜像、幸存临时源码、对话修改回执及重建证据 |
| `/home/yndx/legal-skill-recovery-20261015.8k6bZM` | 文件丢失后首先建立的约 699 MB 原始保全目录，不是新项目 |
| 上述归档目录内同名 `legal-skill-recovery-20261015.8k6bZM/` | 原始保全件的副本；本次整理用 `diff -qr` 核对目录树及全部文件内容一致 |
| `/home/yndx/hhy/legal-skill-backups` → `/media/sangfor/vdb/legal-skill-backups` | 已校验的源码 bundle、配置与实际实验工件备份 |
| `/media/sangfor/vdb/legal-skill-runtime` | 新项目的 Python 运行时，不是另一套业务源码 |
| `/home/yndx/hhy/legal-skill-evolve` | 旧项目幸存残留；旧模型服务参数仍引用它，不搬动、不当作当前工作树 |
| `/home/yndx/hhy/归档.zip` | 用户重新提供的论文相关 skills 原件 |

恢复目录中的 `README.md` 记录的是当时的取证状态，早期 `reconstructed_source_v2/v3`
也只是恢复过程产物，不代表当前代码版本。归档中的旧聊天记录和聚合指标不能替代已丢失的原始模型回执。

本次没有删除任何恢复材料，没有覆盖原始取证文档，也没有移动实际项目、模型路径、
冻结源码、原生输出或教师记录。软链接只是统一访问入口，不增加源码副本。
vdb 上的多个目录不等于已具备异机/离线备份。
