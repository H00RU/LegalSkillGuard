# LegalSkillEvolve

LegalSkillEvolve研究在不微调权重的条件下，能否把冻结Qwen3-8B的组内高低收益多轮轨迹归纳成可复用的法律咨询技能文档，让技能库在顺序经验块中持续积累，并在训练过程与最终官方DLawBench中文30案上，以更少的有效提问取得更多关键事实。来源约束和安全硬门负责保证文档可追溯、可部署，不以小样本逐候选验收阻断技能积累。

论文与文档中的方法名统一为 **LegalSkillEvolve**。为保持历史工件和可复现导入路径兼容，仓库名、Python包`legal_skill_guard`及数据文件前缀暂不重命名；现役完整方法实验臂ID为`legal_skill_evolve`。兼容标识不定义研究重心。

现行协议修订于2026-09-09：128案冻结为8×16顺序经验块。每块结束时，来源合格的结构化候选通过静态合法性、来源因果、安全、去重和提示容量硬门后直接进入工作技能库，下一块自然使用；不再设置`provisional`状态，不做逐候选16/18案配对验收。技能以固定会话提示记忆进入冻结Qwen的会话前调查规划与每个律师决策回合，由模型自主运用；程序既不把文档编译成目标选择规则，也不在模型作答后改写动作。128案训练统一使用合作型客户，四人格只在冻结后的官方外测中检验迁移稳健性。旧执行器、旧轨迹协议和历史run均不能恢复为现行结果。

## 数据与实验边界

- 自建128案全部用于顺序训练，分为8个16案块；每案只属于一个块并统一使用预声明合作型`P_WD`，让客户如实披露律师问题命中的有限事实。
- 每案K=4在同一合作型训练环境、同一块首技能库下独立采样完整调查计划和逐轮策略，用于形成真实组内优势；只保留在F（新客户事实）、G（外部证据缺口）或信息不损失下提问效率上优于低分轨迹的候选来源。
- 当前冻结的官方DLawBench中文30案从未用于运行调试、模型/提示/门槛选择、教师上下文或候选选择，只在最终技能库冻结后外测。它是公开基准，因此这里主张的是严格的held-out执行边界，而不是“研究者从未见过数据”的私有盲测。
- 每块预声明8个合作型案件，以块首工作库的正常K=4结果对匹配空库影子形成prequential开发曲线；曲线不参与教师证据选择或技能准入。第2、4、6、8块后进行库级维护。
- 当前语料是由最高人民法院公开来源约束的AI构建研究语料，不是当事人原话或持证律师专家金标。

核心配置：

- `data/training/legal_skill_guard_dlawbench_style_cn.jsonl`：128案核心语料。
- `data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl`：来源与逐事实证据。
- `configs/data/main_training_batches.yaml`：8×16批次、合作型人格与顺序积累关系的唯一真源。
- `configs/experiments/main_experiment.yaml`：实验、指标、门槛与预算。
- `configs/models/roles.yaml`：LLM及确定性组件角色边界。
- `configs/compliance/china_research_boundary.yaml`：研究原型、信息最小化、事实/法律分离与论文主张边界。
- `skills/bootstrap/`：正式空初始库；运行产物只写入`runs/<run-id>/`。

## 顺序技能积累

1. 第b块以块首工作库`L_(b-1)`运行16案；第一块从空库开始。每案K=4都看到完全相同的适用技能包，只通过冻结Qwen的正常采样形成差异。
2. 健康门只排除泄漏、协议损坏、不可归因fallback、状态错误和不完整K组；健康但表现弱的轨迹仍进入评分，作为TF-GRPO需要的学习信号。
3. 程序从组内高低收益完整轨迹形成通用或领域证据簇。每块最多选3簇；两类证据都存在时至少各选1簇，并优先覆盖不同机制、不同法域且不重复来源fingerprint。
4. Luna对每个入选簇输出一个结构化文档候选或`NOOP`。领域技能只需由对应领域证据支持，不因无法覆盖无关法域而被拒；通用技能仍须有跨法域来源。
5. 候选依次通过静态合法性、来源因果重放、法律与运行安全、语义去重及工作库联合提示容量硬门。通过者在本块结束时直接写入`L_b`，下一块的所有适用轨迹自然看到它；这些硬门不以一次小样本效果决定去留。
6. 每块对块首整体技能库记录prequential效果；第2、4、6、8块后集中做库级去重、冲突与容量维护。第八块仍可产出技能，维护后冻结最终库，再运行官方30案外测。

这里没有“上一块候选占用下一块K=4中的候选/无候选臂”，也没有逐候选16案或18案验收。后一块使用前一块已经入库的全部适用文档；块级空库影子只观察整体库的prequential效果，不反向决定单个候选是否准入。

## 模型角色

- `Qwen/Qwen3-8B`：冻结咨询代理；同一快照的隔离调用承担技能可见的会话前规划、逐轮律师策略、memo，以及只在四人格外测中需要的抗拒披露信号分类。
- `openai/gpt-oss-20b`：权限隔离的客户闭集事实路由与离线语义评审。
- `gpt-5.6-luna`：只从训练证据簇生成候选或`NOOP`，不评分、不看后续块或外测结果，也不自行决定准入。
- 确定性代码：状态、依据分类信号作出的客户披露决定与逐字回答渲染、来源证据绑定、奖励、优势、五类候选硬门、库级维护、哈希和统计。

论文主线以确定性的“唯一新事实/提问”为主终点，并用唯一事实总数、Fact Coverage和Resolution防止少问早停投机；停止机制是防止过早定论和无限循环的安全约束，不是唯一研究主线。批次曲线用于观察技能库逐步充实是否带来效率提升，同时报告安全指标、候选产量、技能文档暴露和技能库规模。文档式干预没有可观测的离散工具调用事件，因此不伪造单技能“使用率”。最终外测至少比较相同冻结Qwen的`control_no_library`与`legal_skill_evolve`；本地单裁判不冒充DLawBench官方多供应商排行榜。

## 文档真源与历史边界

- 现役方法与数据流：`docs/architecture/current_research_protocol.md`。
- 现役评估口径：`docs/architecture/evaluation_contract.md`。
- 现役执行顺序：`docs/operations/main_experiment_execution.md`。
- 现役run产物命名：`docs/architecture/artifact_naming.md`。
- `reports/current_design_cpu_release_audit.md`与`reports/current_skill_model_and_history_audit.md`虽然为兼容旧链接保留原文件名，但标题和首段已经标记为2026-09-08历史快照；正文中的逐候选前瞻、`provisional/DEFER`和每批2项不是现役方案。
- 上级目录的`LegalSkillGuard项目框架与完整实验实施方案.md`是2026-08-18立项蓝图，已在文件首屏标记“历史蓝图·禁止执行”。

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
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> preflight
# 仅当上一步明确报告相应资格证据失效时，才重新运行：
# .venv/bin/python scripts/qualify_client_simulator.py --run-id <run-id>
# .venv/bin/python scripts/qualify_local_judge.py
.venv/bin/python scripts/run_main_experiment.py --run-id <run-id> train \
  --fresh --confirm I_CONFIRM_MAIN_TRAINING
```

客户模拟器允许复用`configs/qualification/client_simulator_evidence.yaml`显式批准的组件级资格证据，
但preflight会逐项核对报告、binding、提示、schema、实现、模型revision、资格样例及端点身份的当前
哈希；任一项变化都必须为当前run重新资格。裁判资格同样按当前完整组合哈希验证。换run ID本身不
要求重复消耗GPU，旧哈希、仅文件同名或历史成功结论都不能替代当前验证。`train`入口还会自动执行
一次结构化教师与裁判探针，不需要在它之前重复带`--probe-codex`的preflight。

同一现行run安全中止后才可使用`--resume`；任何实现或协议变化都必须换新run ID。旧64条首轮、20条完整对话、128案调查计划及其语义审计入口已从现行代码和配置删除；历史输出只可留在隔离档案中，不能执行、恢复或计入结果。
