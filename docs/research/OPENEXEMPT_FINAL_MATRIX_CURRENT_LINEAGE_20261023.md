# 正式测试矩阵：当前来源、比较关系与执行交接

2026-10-23。根据14:57的实际源配置核对结果整理；状态是当时快照，不是实时进程判断。
这是已声明实验的交接文件，不新增方法、任务、种子或比较，不是可执行TEST配置。
当前主方法完整八批结果保留，正式测试仍封存。

## 实验顺序与来源

后台顺序：ACE45末批 → 固定静态库完整TRAIN对照 → Text45完整构建 →
whole-bank及first-commit两项消融 → 主145/ACE145/主245/ACE245/Text145/Text245。
每个阶段均要求上个阶段真实自然完成、完整终态与双盘保存；失败不会当作完成。

最终16个条件来自12份学习/编译源配置，不是16种方法或16个独立数据集。
三个主学习器各提供自己的B1和B8两个库，B1不是额外学习，也不是选取最好的早期库。
静态库直接使用零案件编译的原出版物；静态TRAIN对照不再训练或重写它。

| 条件 | 源配置 | 唯一固定出版物 | 来源状态 |
|---|---|---|---|
| `empty`（强空库） | 无 | `空文本` | 不需要学习 |
| `static`（盲法条静态库） | [direct_law_only_static_20261021_run03](../../configs/openexempt_direct_law_only_static_20261021_run03.json) | `publication.json` | 已完成 |
| `main45`（主方法） | [closed_feedback_public_assets128_20261021_run03](../../configs/openexempt_closed_feedback_public_assets128_20261021_run03.json) | `publications/b8.json` | 已完成 |
| `own_B1_45`（自身B1冻结） | [与对应主方法同源](../../configs/openexempt_closed_feedback_public_assets128_20261021_run03.json) | `publications/b1.json` | 已完成 |
| `ACE45`（经验学习） | [ace_public_assets128_20261023_run04](../../configs/openexempt_ace_public_assets128_20261023_run04.json) | `publications/b8.json` | B8进行中 |
| `text45`（经验学习） | [trace2skill_text_public_assets128_seed45_20261023_run02](../../configs/openexempt_trace2skill_text_public_assets128_seed45_20261023_run02.json) | `publications/final.json` | 待执行 |
| `main145`（主方法） | [closed_feedback_public_assets128_seed145_20261023_run02](../../configs/openexempt_closed_feedback_public_assets128_seed145_20261023_run02.json) | `publications/b8.json` | 待执行 |
| `own_B1_145`（自身B1冻结） | [与对应主方法同源](../../configs/openexempt_closed_feedback_public_assets128_seed145_20261023_run02.json) | `publications/b1.json` | 待执行 |
| `ACE145`（经验学习） | [ace_public_assets128_seed145_20261023_run02](../../configs/openexempt_ace_public_assets128_seed145_20261023_run02.json) | `publications/b8.json` | 待执行 |
| `text145`（经验学习） | [trace2skill_text_public_assets128_seed145_20261023_run02](../../configs/openexempt_trace2skill_text_public_assets128_seed145_20261023_run02.json) | `publications/final.json` | 待执行 |
| `main245`（主方法） | [closed_feedback_public_assets128_seed245_20261023_run02](../../configs/openexempt_closed_feedback_public_assets128_seed245_20261023_run02.json) | `publications/b8.json` | 待执行 |
| `own_B1_245`（自身B1冻结） | [与对应主方法同源](../../configs/openexempt_closed_feedback_public_assets128_seed245_20261023_run02.json) | `publications/b1.json` | 待执行 |
| `ACE245`（经验学习） | [ace_public_assets128_seed245_20261023_run02](../../configs/openexempt_ace_public_assets128_seed245_20261023_run02.json) | `publications/b8.json` | 待执行 |
| `text245`（经验学习） | [trace2skill_text_public_assets128_seed245_20261023_run02](../../configs/openexempt_trace2skill_text_public_assets128_seed245_20261023_run02.json) | `publications/final.json` | 待执行 |
| `whole_bank`（独立学习消融） | [whole_bank_public_assets128_20261023_run02](../../configs/openexempt_whole_bank_public_assets128_20261023_run02.json) | `publications/b8.json` | 待执行 |
| `first_commit`（独立学习消融） | [first_commit_public_assets128_20261023_run02](../../configs/openexempt_first_commit_public_assets128_20261023_run02.json) | `publications/b8.json` | 待执行 |

主方法、ACE、文本适配各有45/145/245三次独立学习；两个消融各只有seed45一次学习。
ACE45经过两次明确的运行恢复，但仍是原空库起点的一条学习轨迹，不计成多个重复。
每个方法的实际末库必须自然完成，不用缺失填零、不挑最好seed或中间库。

## 正式性能主表与学习过程表

正式主表：全部库冻结后，在同一128个独立训练外来源上，EC/EV各回答一次。
所有16臂共4096个逻辑预测；同完整请求的物理响应复用不增加独立n。
执行器是同一个冻结8B，共同测试推理seed45；不是每个库解码三遍。

八批曲线：训练流的首次遇案表现，含同案强空库及每次学习自己的B1对照。
训练内纠错和已见来源重放单独展示，不能替代首答或正式测试。
文本适配一次性构建末库，不硬画成八次在线进化曲线。

当前已有主方法与ACE完整128案的首答对照。它说明学习过程中已有差异，
不能据此填TEST主表、宣布最终库胜出、跨学习运行显著或官方SOTA。

## 固定的比较方向

每项都是“完整主方法减对照”，EC、EV分开计算。五组主要比较共十个终点比较：

| 主要比较 | 完整主方法一侧 | 对照一侧 |
|---|---|---|
| 技能净收益 | main45/main145/main245等权均值 | 一个共同强空库 |
| 超过静态提示 | 同上 | 一个盲法条静态库 |
| 持续进化 | 同上 | 按学习seed对应的三个自身B1库 |
| 在线经验方法 | 同上 | ACE45/ACE145/ACE245等权均值 |
| 轨迹归纳方法 | 同上 | text45/text145/text245等权均值 |

两项次要比较只用主方法seed45，不能拿三次主方法均值对单次消融：

- main45 − whole_bank：公开法律情境的分量提交与整库提交。
- main45 − first_commit：保留失败反馈并细化，与首次成功提交后不再细化。

消融包含各自重新从空库进行的完整八批学习，不是删除主末库几条技能后作答。
实际提案、重放与计算量仍可能不同，不能把差异写成纯信息或等实际计算的因果效应。

## 指标、区间和结论

原OpenExempt EC/EV F1保持不变，先按原规则在案内聚合，再对128个来源等权平均。
主要比较先对三组真实学得库取同源差值均值，再对来源求均值。
共享空库/静态库只有一个真实对照分数，不复制成三份独立生成。

来源配对cluster bootstrap：20000抽样，NumPy PCG64 seed2026102192，linear quantile。
普通双侧95%区间；十个主要比较的调整尾分位为0.0025/0.9975，
四个次要比较为0.00625/0.99375。区间条件于这批已学得库和固定解码，
不是整个学习算法总体变异的区间；三次学习的逐次结果和范围须同时报告。

另报完整输出F1、负目标/未计分资产误引、格式错误、截断、同案损害、实际技能
增改/拒收/NOOP、技能投递及真实调用/token/墙钟。推理token若已计入输出不重复相加。
原无效回答按既有评分保留；没有获得的预测和完整性错误不冒充正常零分。

只有实际支持的比较才作相应结论。ACE/Trace2Skill是已披露的法律任务适配；
不能延伸为超越作者默认完整系统、未复现SkillCommit或所有技能学习方法。

## 本轮已核实和仍未完成

已用实际12份源配置调用当前正式评价器的协议/对照检查，16条件均通过；
主方法重复改算法、自身B1错配来源、单次消融错误对三次主均值的三个负例均拒绝。
所有实际答题/scoring源身份已核对；教师日志专用改动以原源码和AST单独校验，
不冒称原共享文件全部逐字未变。

[实际16条件来源与比较核对](../../artifacts/research/openexempt_legal_scope_20261020/final16_current_lineage_actual_source_protocol_primary10_secondary4_plan_NOT_TEST_config_20261023.json)
保存精确config/freeze哈希、比较数组、预期出版物及重算程序。
它不证明尚未完成的库已经合格；当前可用来源出版物为主45末库、自身B1和静态库。

仍须：全部实际学习与消融完成、实际末库和终态存档齐全、完整16臂配置与统计/源码
正式冻结，才可预测TEST。实际可执行最终配置尚不存在，不能运行占位文件名。
当前模型maxseq1不动；未来单实例四请求调度依原协议另行捕获环境后才能使用。

正式入口仍是隔离worktree的 `experiments/openexempt_frozen_eval.py`，source f138029；
从canonical目录运行并设置canonical PYTHONPATH，不能导入旧worktree数据或旧根目录CLI。
嵌套恢复链、旧零分、退役调用及原始空库起点都必须通过，CPU106项通过不代替实际全矩阵。

## 依据

- [原分析计划](OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md)与
  [文本方法/十主要比较增补](OPENEXEMPT_FINAL_ANALYSIS_TEXT_COMPLEMENT_ADDENDUM_20261022.md)；
- [同版本教师超时恢复](OPENEXEMPT_ACE_TEACHER_TIMEOUT_CONTINUATION_20261023.md)；
- [最终单实例调度边界](OPENEXEMPT_FROZEN_EVAL_SINGLE_INSTANCE_DISPATCH_20261023.md)。

实验设计规范用于研究问题、对照、机制证据、成本和结论对应；
不为凑模板新增OOD、跨骨干、五次重复或未经证明的命题。
