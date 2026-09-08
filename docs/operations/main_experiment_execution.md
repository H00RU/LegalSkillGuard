# 主实验执行说明（128案顺序前瞻）

现行协议为8批×16案。没有固定内部验收集，也没有逐候选额外对话。

| 环节 | 数据 | 作用 |
|---|---|---|
| 顺序训练 | 自建128案，8批×16案 | K=4轨迹、组内优势、候选来源 |
| 内嵌前瞻 | 第2—8批正常轨迹 | 验证紧接前一批候选 |
| 开发曲线 | 每批预声明8案 | 当前正式库－空库诊断 |
| 主外测 | 官方中文30案×4人格 | 冻结库后的最终比较 |

## 每批顺序

1. 冻结本批输入正式库。若有上一批候选，按候选法域和冻结案件顺序预先分配适用案件。
2. 一次生成完整16×K4轨迹和memo。共享对照看到正式库；候选治疗从首轮起看到正式库加一个候选；其余臂继续探索。
3. 在评分前验证轨迹健康和唯一干预：会话技能文档ID及哈希固定，旧运行时技能执行字段必须为空。
4. 完成离线评分；用本批共享对照处理上一批候选的实际收益、F/G/效率机制、有害尾与安全结果，得到`ACCEPT/DEFER/REJECT`。
5. 正式接收项写入新库版本；`DEFER`继续占用后续适用案件，最多累计3块；拒绝项不进入库。
6. 对本批正常K=4计算组内优势，确定性形成F/G/safe-stop证据簇。最多向Luna提交两个行为机制不同的合格簇；允许`NOOP`。
7. 新候选通过静态门、安全门和来源见证后写为`provisional`，只能由下一未见块验证，不能在来源批自证。
8. 写入不可变批次检查点和开发曲线点，再进入下一批。

第八批只处理第七批候选并冻结技能库，不产生无法前瞻验证的新候选。“前一批生成、后一批验证”的设计保持不变；改变的只是技能从旧的作答后规则改写切换为每轮固定提示文档。

## 启动与恢复

```bash
bash scripts/start_main_model_services.sh
.venv/bin/python scripts/qualify_client_simulator.py --run-id <run-id>
.venv/bin/python scripts/qualify_local_judge.py
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> preflight --probe-codex
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> train \
  --fresh --confirm I_CONFIRM_MAIN_TRAINING
```

以上四个准备步骤不可换成历史结果：客户资格必须写入同一`<run-id>`，本地裁判资格必须与当前
提示、schema、评分实现和冻结revision的组合哈希一致。资格失败时先保留失败报告并定位组件，
不得启动正式训练，也不得用旧资格报告覆盖。

安全中止后只能在实现、配置、模型、数据、提示、批次计划和空初始库哈希全部仍一致时恢复：

```bash
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> train \
  --resume --confirm I_CONFIRM_MAIN_TRAINING
```

任何协议切换必须使用新run ID。旧调查计划、64条首轮、20条完整对话及其语义审计入口已从现行代码和配置删除；历史输出与历史run都不能执行、恢复或作为效果证据。
