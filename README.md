# LegalSkillGuard

LegalSkillGuard研究在不微调权重的条件下，能否把冻结Qwen3-8B的结构化反事实多轮轨迹归纳成可复用的法律咨询技能文档，并在后续未见案件和最终官方DLawBench中文30案上，提高事实调查与问题解决能力，同时控制幻觉、重复追问和过早结束。

现行协议修订于2026-09-08：128案、8×16顺序批次及“前一批生成候选、后一批未见案件前瞻验证”保持不变。技能的在线使用已统一为固定会话提示记忆：每个律师决策回合都提供相同的适用技能文档包，由冻结Qwen自主运用；模型作答后不存在技能规则执行或动作改写。旧执行器、旧轨迹协议和历史run均不能恢复为现行结果。

## 数据与实验边界

- 自建128案全部用于顺序训练，分为8个16案块；每案只属于一个块并使用一个预声明人格。
- 每案K=4形成共享可见调查计划下的受控轨迹组，用于组内优势和F（新客户事实）、G（外部证据缺口）、safe-stop证据归因。
- 当前冻结的官方DLawBench中文30案从未用于运行调试、模型/提示/门槛选择、教师上下文或候选选择，只在最终技能库冻结后外测。它是公开基准，因此这里主张的是严格的held-out执行边界，而不是“研究者从未见过数据”的私有盲测。
- 每批预声明8个哨兵案形成当前正式库相对空库的开发曲线；曲线不参与教师或候选准入。
- 当前语料是由最高人民法院公开来源约束的AI构建研究语料，不是当事人原话或持证律师专家金标。

核心配置：

- `data/training/legal_skill_guard_dlawbench_style_cn.jsonl`：128案核心语料。
- `data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl`：来源与逐事实证据。
- `configs/data/main_training_batches.yaml`：8×16批次及相邻前瞻关系的唯一真源。
- `configs/experiments/main_experiment.yaml`：实验、指标、门槛与预算。
- `configs/models/roles.yaml`：LLM及确定性组件角色边界。
- `skills/bootstrap/`：正式空初始库；运行产物只写入`runs/<run-id>/`。

## 顺序技能生命周期

1. 第一批从空库生成轨迹并评分。
2. 程序从同状态优劣轨迹形成合格证据簇；Luna每次可提出一个最小候选或`NOOP`，每批可处理多个不同机制簇。
3. 候选通过静态合法性、安全检查、重复性检查和来源证据绑定后成为`provisional`。来源见证只确认文档来自合格因果对照，不要求文档精确复现某个旧动作，也不参与在线律师决策。
4. 下一未见块中，共享对照看到当前正式库；治疗轨迹从首轮起看到“当前正式库+候选”。两者共享案件、人格、调查计划、模型revision和随机流。
5. 根据配对收益、事实/证据缺口/提问效率机制、安全和有害尾决定`ACCEPT/DEFER/REJECT`。通过项从再下一批进入正式库；安全正向但覆盖不足者最多累计3块。
6. 第八批只验证第七批候选，不生成无法继续验证的新候选。冻结技能库后才运行官方外测。

这不是“每个候选另跑18案”。候选验证嵌在下一批正常训练轨迹里，同一份数据既推进训练，也给上一批候选提供未见证据。

## 模型角色

- `Qwen/Qwen3-8B`：冻结律师策略；同一快照的隔离调用还承担共享咨询规划、抗拒人格披露信号分类和memo。
- `openai/gpt-oss-20b`：权限隔离的客户闭集事实路由与离线语义评审。
- `gpt-5.6-luna`：只从训练证据簇生成候选，不评分、不验收、不写正式库。
- 确定性代码：状态、依据分类信号作出的客户披露决定与逐字回答渲染、来源证据绑定、奖励、优势、前瞻门禁、哈希和统计。

论文主线以确定性的“唯一新事实/提问”为主终点，并用唯一事实总数、Fact Coverage和Resolution防止少问早停投机；同时报告安全指标、候选转化和技能库规模。最终外测包含`control_no_library`、`ungated_source_grounded_skills`和`legal_skill_guard`。本地单裁判不冒充DLawBench官方多供应商排行榜。

## 静态审计与测试

```bash
.venv/bin/python scripts/build_court_source_pool.py --verify-only
.venv/bin/python scripts/build_main_corpus.py
.venv/bin/python scripts/audit_main_corpus_casewise_quality.py
.venv/bin/python scripts/audit_main_corpus_contamination.py
.venv/bin/python scripts/audit_training_batches.py
.venv/bin/python scripts/audit_paper_protocol.py
.venv/bin/python -m pytest -q
```

## 新run

```bash
bash scripts/start_main_model_services.sh
.venv/bin/python scripts/qualify_client_simulator.py --run-id <run-id>
.venv/bin/python scripts/qualify_local_judge.py
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> preflight --probe-codex
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> train \
  --fresh --confirm I_CONFIRM_MAIN_TRAINING
```

客户资格报告与同一个新run绑定；本地裁判资格报告绑定当前裁判提示、schema、实现、模型revision和
冻结资格样例。两者均通过后preflight才会放行，历史资格文件不能替代这一步。

同一现行run安全中止后才可使用`--resume`；任何实现或协议变化都必须换新run ID。旧64条首轮、20条完整对话、128案调查计划及其语义审计入口已从现行代码和配置删除；历史输出只可留在隔离档案中，不能执行、恢复或计入结果。

完整现行定义见[`docs/architecture/current_research_protocol.md`](docs/architecture/current_research_protocol.md)，评估口径见[`docs/architecture/evaluation_contract.md`](docs/architecture/evaluation_contract.md)，执行顺序见[`docs/operations/main_experiment_execution.md`](docs/operations/main_experiment_execution.md)。
