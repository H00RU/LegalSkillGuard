# LegalSkillEvolve — current legal evidence skill learning

Status: current core reconstructed after the 2026-10-15 file-loss incident.
The checkpoint-fork study and its delivery probe are complete; neither establishes
stable benefit over strong empty memory. The bounded ACE/ExpeL comparison was
restarted as `legal_contractnli_adaptive_memory_comparison_20261015_run02` after
a transport-schema rejection. Its first two teacher responses are now complete.
This is ordinary user-directed work, not active Goal mode, and not a new long
paper-training run. The old failure and its costs remain preserved.

The target is the latest ContractNLI legal-evidence learning pipeline, not the
2026-09-27 multi-turn consultation task. The executor remains a frozen Qwen3-8B;
the existing authorized teacher evolves explicit skills from seen training
source/labels and actual public trajectories. No parameter fine-tuning, hidden
answer repair, fallback bank, effect-based admission, or fabricated old results.

Canonical project location: `/media/sangfor/vdb/legal-skill-evolve`.
Daily workspace entry: `/home/yndx/hhy/legal-skill-current` (a symlink, not a copy).
See [project locations and active runs](docs/PROJECT_LAYOUT.md) before starting work.
Historical source evidence and failed experiments remain separately preserved.
Recovered code and rebuilt dependencies are not a recovery of lost raw model
responses. A new experiment must use a new Run ID and record its actual outputs.

The research target remains a credible legal-domain skill-learning study for an
SCI Q3-or-better journal: demonstrate transfer to disjoint sources against a
strong empty-memory model and credible experience-learning baselines, with
complete label/evidence/joint metrics, costs, failures, and attribution. These
are objectives to test, not promises of monotonic gains or publication.

## 已核验与未完成

13项无模型调用的边界测试通过（本轮0.31秒）；一份训练合同完成真实的律师回答→强教师
差分编辑→技能查询执行→律师重答，独立评分与实际传递核验一致。
另有幸存旧请求逐字消息／Schema及6212-token计数核对；不是只凭聊天记录猜实现。
这些是重建核验，不是方法已优于空库或ACE的证据。

旧训练原始记录和完整末次技能库仍有缺失，不回填旧Run ID或论文成绩。
本地8B权重文件尚缺，当前使用同一个仍运行的原服务；不能宣称已具备重启后的完整离线环境。

## 使用

日常入口：

```bash
cd /home/yndx/hhy/legal-skill-current
```

当前有限试验使用独立 Run ID 和冻结 worker，详见目录说明中的当前后台工作；
直接查看各自的 `runs/<Run ID>/progress.json` 及实际完成工件，不要重复启动。
当前运行协议：[Schema修正后的有限对照](reports/experiments/adaptive_memory_comparison_20261015_run02/protocol.md)。
当前进度文件：`runs/legal_contractnli_adaptive_memory_comparison_20261015_run02/progress.json`。

CLI 的 `status`／`launch` 对应 `configs/contractnli_main.json` 中另外保留的完整
32训练来源／8批与24来源六条件比较（388次律师、57次教师），不是当前后台分叉试验。
这轮完整比较尚未启动，不能将配置存在误认为正式实验已经完成。

单案工程核验的记录位于
`runs/legal_reconstruction_chain_check_20261015_run01/engineering_completion.json`；
其代码和旧配置快照独立保存，正式入口使用`configs/contractnli_main.json`。

详见[方法与边界](docs/METHOD_AND_PROTOCOL.md)、[历史决策](docs/HISTORY_DECISIONS.md)
及[重建交付记录](docs/REBUILD_STATUS.md)。师兄的方法／实验技能用于机制—代码一致性和公平对照检查，
没有照搬模板中的固定贡献数、重复次数或示例成绩。
日常论文技能以hhy下`paper-skills/`为当前版本；`归档/`是旧版本保全，不同时混用。
见[两版本逐项比较](reports/audits/paper_skill_versions_20261015.md)。
