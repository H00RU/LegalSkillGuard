# LegalSkillGuard 研究交接

本页是服务器与 GitHub 研究分支的唯一进度入口。2026-11-21 核对。后续由普通对话推进 M1，M2 挂起。

## 当前版本

- 服务器工作区为 `/home/yndx/hhy/legal-skill-current`，本地与 GitHub 使用 `research/paired-interface-structural-transfer-20261116`。整理前本地 HEAD 为 `57ee24fd1548d11ac069bdfae78a90584d57abd3`，GitHub HEAD 为 `6128e4ad994e970fb3ff5fc97cb3a7714fecf2a6`。最新 M1 代码及其运行依赖在服务器；本次同步入口文档并移除五个旧可行性脚本。
- 最新已结算版本为 `m1_cni_origin_citation_formal_055f3700`。它将 ContractNLI 独立开发和第三方取得的分项引文接回相应主条款，各臂使用同一原文证据，用前批 TRAIN 拟合采纳策略。绑定 `18cac94caf5fcd90022ca333c226a4e7bd1f5b39a1bdac30bc6439cf7935c5a1`，终态封印 `1f603ff35cc05ce7f79782d50ef68e57dfa69b9ca854158fda9b9064af72e55d`。

## 当前运行交接

- `legal-skill-m1` socket 下的 `m1-origin-citation-20261121` 已退出，退出码 0。TRAIN B1–B8 和五库固定 DEV 已结算，无待续批次或在途研究作业。连续账本 `artifacts/rr_v2_preflight/research_ledger.sqlite3` 有 16,106 笔完成、37 笔历史失败、0 笔在途。本轮整理与最新版本均新增 0 笔模型请求。
- 原 128 个 TRAIN 来源、8 批、592 个原生项；固定 DEV 为 80 个来源、384 个原生项。最新版本复用原教师与执行器读数，保留冻结 Qwen3-8B、thinking OFF。

## 已结算结果

| 库／指标 | M1 TRAIN | M1 固定 DEV B8 |
| --- | ---: | ---: |
| ContractNLI 分类／正确类引文 F1 | 387/408 ／ 83.08% | 264/272 ／ 83.12% |
| MAUD 知识定义／负面临时契约／正常经营契约 | 24/24 ／ 24/24 ／ 23/24 | 16/16 ／ 13/16 ／ 14/16 |
| OpenExempt 资格／估值 F1 | 97.07% ／ 98.41% | 100% ／ 100% |
| RuleArena Airline 原生准确率 | 24/24 | 16/16 |
| LegalBench Diversity 原生准确率 | 24/24 | 16/16 |

ContractNLI 固定 DEV 引文 F1 与上一版及本轮不拟合消融同为 83.12%。同信息固定及直接对照均为 80.80%，M1 累计差值为 +2.32 个百分点，按母来源配对的 95% 区间为 [1.12, 3.57]。本轮不拟合消融的 TRAIN 为 83.69%，高于拟合臂的 83.08%。五库逐项独立收益尚未验收；原冻结 TEST 已结算并登记曝光。 [原冻结 TEST 计分](../reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_NATIVE_TABLES.md) · [冻结证据清单](../reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_EVIDENCE_MANIFEST.json)

## 结果与复现路径

以下命令在服务器上只读核对。

```bash
cd /home/yndx/hhy/legal-skill-current
tmux -L legal-skill-m1 list-panes -a -F '#{session_name} #{pane_pid} #{pane_dead} #{pane_dead_status}'
base=artifacts/legal_skill_convergence_20261117
pointer="$base/handoff/m1_cni_origin_citation_formal_055f3700_current.json"
out=$(.venv/bin/python -c 'import json, sys; print(json.load(open(sys.argv[1]))["artifact_root"])' "$pointer")
cat "$pointer"
ls "$out"/{binding.json,terminal.json,source_snapshot,train/B{1..8}/receipt.json,train/B{1..8}/library.json,dev/B8/receipt.json}
tail -n 12 "$base/handoff/m1_job_logs/m1-origin-citation-20261121.log"
```

原八批正式入口是 `experiments.convergence_m1_formal`，当前绑定入口是 `.venv/bin/python -u -m experiments.convergence_m1_cni_origin_citation_formal`。当前入口先核对父版本终态、研究绑定、原队列和驱动锁，再读取已结算终态；需要重建时从已封存的父版本读数按批次顺序回放。五库评分通过 `grade_view`，OpenExempt 用独立工作进程加载已固定的官方 scorer。服务器的冻结范围文本和研究协议继续用于校验原运行绑定。 [公开方案](../reports/legal_skill_convergence_20261117/PLAN.md) · [公开接续协议](../reports/legal_skill_convergence_20261117/continuation_protocol_20261119.json) · [冻结协议](../reports/legal_skill_convergence_20261117/protocol.json)

工作树归档、旧入口原文、依赖核对和离线回放回执位于服务器的 `artifacts/legal_skill_convergence_20261117/handoff/workspace_cleanup_20261121/`。

## 历史尝试索引

| 尝试 | 结论与复现版本 |
| --- | --- |
| Lift／CoRev、C 及观察契约 | 固定流程有整体收益，目标机制的独立收益未建立，旧队列已停止。 [停止复盘与证据](https://github.com/H00RU/LegalSkillGuard/blob/6128e4ad994e970fb3ff5fc97cb3a7714fecf2a6/reports/legal_skill_evolution_run_20261111/component_training_20261115/GOAL_RETROSPECTIVE_20261116.md) |
| 11 月 17 日 M1 自动配对接口 | OpenExempt 有限 TRAIN 诊断 F1 为 1/3，完整正确 0/4，正分涉及将源审的 unknown 断言为 true，停止扩展。旧小试驱动、归因、打包和两条回放入口已退出当前树。 [固定提交的决定](https://github.com/H00RU/LegalSkillGuard/blob/1f132108fa326d46118c3c708458fbbafec7bfb2/reports/two_method_followthrough_20261116/M1_FEASIBILITY_DECISION_20261117.md) · [两条离线复现命令](https://github.com/H00RU/LegalSkillGuard/blob/1f132108fa326d46118c3c708458fbbafec7bfb2/reports/two_method_followthrough_20261116/M1_finite_evidence_20261117/README.md) · [历史打包脚本](https://github.com/H00RU/LegalSkillGuard/blob/354bece66fd9a0b1e7bc8dab1a6d7159ee141345/experiments/m1_build_evidence_packet.py) |
| 收敛方案原冻结矩阵 | 五库冻结验证已结算。Diversity 的 M1 平衡准确率差值为 +12.50 个百分点，95% 区间包含零；M2 两组原生预测逐项相同。旧轮次保留原版本和曝光登记，当前 M2 挂起。 [固定提交的计分](https://github.com/H00RU/LegalSkillGuard/blob/6128e4ad994e970fb3ff5fc97cb3a7714fecf2a6/reports/legal_skill_convergence_20261117/paper/tables/TEST_B8_NATIVE_TABLES.md) |

## 下一步

在普通对话中从最新 B8 终态接续 M1。先逐来源核查 ContractNLI 拟合臂与不拟合消融的 TRAIN 差异，确认哪些引文修订有可迁移的前批证据，再决定下一项比较。复用已结算的同条件结果，保持同信息、同预算对照；修订依据使用 TRAIN 和固定 DEV，保留旧 TEST 的曝光边界。M2 挂起。
