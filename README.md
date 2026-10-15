# LegalSkillEvolve — current legal evidence skill learning

Status: current core reconstructed after the 2026-10-15 file-loss incident.
The checkpoint-fork study, delivery probe and bounded ACE/ExpeL comparison are
complete. None establishes stable overall benefit over strong empty memory.
The complete draft-review study found small joint gains, but no evidence-F1 gain
over equal-call empty review. Mandatory source-check outputs then produced harmful
evidence-set copying and were stopped at16:37 after three complete batches.
The compact delivery diagnostic completed at17:28, with36 new lawyer calls.
It did not beat strong empty memory overall: evidence F1/joint fell from61.48/46.32
to54.39/35.29 with ranked candidates plus text skills. All adverse outputs remain.
The tree-query study stopped at18:36:45 after14 lawyer responses: all47 learned
queries were mathematically inert, despite good seen-case supervised fit.
The next study preserves the same-data word/calibration model and learns only
additional query coefficients; see [query-memory protocol](docs/QUERY_MEMORY_METHOD.md).
The zero-query diagnostic exactly restores the ordinary tool. This functional
repair has not yet shown a development-set F1 gain and is not a claimed success.
Its external evidence scorer is supervised and learns weights; the lawyer remains
frozen. It is NOT pure verbal skill learning or an established improvement.
No host repair, best-bank rollback, extra LLM or new legal task is introduced.
At15:09 the user
explicitly requested a new Goal, which is active; see [current Goal](docs/CURRENT_GOAL.md).
Neither starting a Goal nor implementing a method proves benefit. Old failures,
raw answers and their costs remain preserved.

The target is the latest ContractNLI legal-evidence learning pipeline, not the
2026-09-27 multi-turn consultation task. The executor remains a frozen Qwen3-8B;
the existing authorized teacher evolves explicit skills from seen training
source/labels and actual public trajectories. No lawyer parameter fine-tuning, hidden
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

20项无模型调用的边界测试通过（本轮2.07秒）；一份训练合同完成真实的律师回答→强教师
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

当前CLI默认配置：`configs/contractnli_query_memory.json`。
运行ID：`legal_contractnli_query_memory_learning_20261015_run01`。
四批每批6份TRAIN，122新律师/5教师，另12显式相同冷输入观察共享。
用`.venv/bin/python -m legal_skill_guard.cli status`查真实状态；配置存在不等于已启动。
当前源码不得在worker运行中热改。该开发学习研究不是正式论文比较或已证明优于空库。
前一[紧凑交付诊断](reports/experiments/compact_evidence_delivery_20261015/protocol.md)
已完成；36新律师/0教师，最终结果和完整独立审计保留。

旧[原文核查式技能执行](docs/SOURCE_CHECK_METHOD.md)Run保留26新律师/3教师，
B3出现依据FP激增与联合损害，已停止；[停止审计](reports/experiments/source_check_20261015/stopped_readout.md)。
旁路CPU定位有正排序信号，但不是最终F1或纯文字技能收益，不能自动补进律师答案。

旧[面向实际答案的技能复核](docs/ANSWER_REVIEW_METHOD.md)及`contractnli_review.json`保留为历史。
15:31:45完成56次新律师、4教师和后续24答，依据问题未解决；15:41:06完成10调用锚定诊断。
两者原始响应、源码快照与不利结果不覆盖。旧冻结配置绑定旧源码，不用当前代码冒充历史重放。

`configs/contractnli_main.json`仍保留旧32训练／8批、24来源六条件配置（388次律师、57次教师），
尚未启动，不是当前默认入口。旧冻结配置绑定旧源码，不能直接冒充本修订的正式实验。

单案工程核验的记录位于
`runs/legal_reconstruction_chain_check_20261015_run01/engineering_completion.json`；
其代码和旧配置快照独立保存，不是当前默认实验。

详见[方法与边界](docs/METHOD_AND_PROTOCOL.md)、[历史决策](docs/HISTORY_DECISIONS.md)
及[重建交付记录](docs/REBUILD_STATUS.md)。师兄的方法／实验技能用于机制—代码一致性和公平对照检查，
没有照搬模板中的固定贡献数、重复次数或示例成绩。
日常论文技能以hhy下`paper-skills/`为当前版本；旧`归档/`已不存在，助手未删除，不依赖该目录。
见[两版本逐项比较](reports/audits/paper_skill_versions_20261015.md)。
