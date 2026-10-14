# LegalSkillEvolve — current legal evidence skill learning

Status: current core reconstructed and one real learning cycle verified after
the 2026-10-15 file-loss incident. Full research comparison has not been rerun.

The target is the latest ContractNLI legal-evidence learning pipeline, not the
2026-09-27 multi-turn consultation task. The executor remains a frozen Qwen3-8B;
the existing authorized teacher evolves explicit skills from seen training
source/labels and actual public trajectories. No parameter fine-tuning, hidden
answer repair, fallback bank, effect-based admission, or fabricated old results.

Canonical project location: `/media/sangfor/vdb/legal-skill-evolve`.
Historical source evidence and failed experiments remain separately preserved.
Recovered code and rebuilt dependencies are not a recovery of lost raw model
responses. A new experiment must use a new Run ID and record its actual outputs.

The research target remains a credible legal-domain skill-learning study for an
SCI Q3-or-better journal: demonstrate transfer to disjoint sources against a
strong empty-memory model and credible experience-learning baselines, with
complete label/evidence/joint metrics, costs, failures, and attribution. These
are objectives to test, not promises of monotonic gains or publication.

## 已核验与未完成

11项无模型调用的边界测试通过；一份训练合同完成真实的律师回答→强教师
差分编辑→技能查询执行→律师重答，独立评分与实际传递核验一致。
另有幸存旧请求逐字消息／Schema及6212-token计数核对；不是只凭聊天记录猜实现。
这些是重建核验，不是方法已优于空库或ACE的证据。

旧训练原始记录和完整末次技能库仍有缺失，不回填旧Run ID或论文成绩。
本地8B权重文件尚缺，当前使用同一个仍运行的原服务；不能宣称已具备重启后的完整离线环境。

## 使用

在本目录执行：

```bash
.venv/bin/legal-skill status
.venv/bin/legal-skill launch
.venv/bin/legal-skill status
```

`launch`才会后台启动新Run的完整32训练来源／8批与24来源六条件终点比较，
计划388次律师、57次教师；源码先冻结，不自动重试、择库或回滚。
当前没有启动这轮完整比较。逐批结果会自动写入对应run的`results.md`和`training_curve.csv`。

单案工程核验的记录位于
`runs/legal_reconstruction_chain_check_20261015_run01/engineering_completion.json`；
其代码和旧配置快照独立保存，正式入口使用`configs/contractnli_main.json`。

详见[方法与边界](docs/METHOD_AND_PROTOCOL.md)、[历史决策](docs/HISTORY_DECISIONS.md)
及[重建交付记录](docs/REBUILD_STATUS.md)。师兄的方法／实验技能用于机制—代码一致性和公平对照检查，
没有照搬模板中的固定贡献数、重复次数或示例成绩。
