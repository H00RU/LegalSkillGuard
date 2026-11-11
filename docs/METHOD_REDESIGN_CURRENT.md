# 当前证据与下一项实际工作

Goal **active、未完成**。唯一目标与验收见[CURRENT_GOAL.md](CURRENT_GOAL.md)。执行目录`/home/yndx/hhy/legal-skill-redesign-20261109`，分支`research/legal-skill-evolution-20261111`；main不修改。历史暂停已解除，不是当前队列。

## 当前结论

固定20个TRAIN母来源、4批、4个学习臂的**首遍已经完成**，共16次更新结算，原始结果保持。Full/FreeEvolution/AllPorts+CoRev/Lift+GenericJoint最终分别有2/3/2/0个已接纳技能，CoRev模式均为0。Full的专门Lift修订为0。已有真实获取与执行，但两项独立机制与强对照增量均未成立。正式128来源/8批七系统流程已完成B1/B2更新，正在接续B2 DEV及后续批次；TEST仍封存，Goal未完成。

| 臂 | 接纳技能 | 批初新母来源原生核心正确/50视图 | 原生fallback/50 | CoRev模式 |
|---|---:|---:|---:|---:|
| Full | 2 | 0 | 50 | 0 |
| FreeEvolution | 3 | 0 | 50 | 0 |
| AllPorts+CoRev | 2 | 0 | 48 | 0 |
| Lift+GenericJoint | 0 | 0 | 50 | 0 |

AllPorts另外2次批初主路径执行均错误，不能计成功。训练后回放的成功与批初新来源严格分开：自由演化在B1原OE母来源EC/EV官方F1均为1；Full在B2把一条SARA由错改对，全端口对照把两条改对，覆盖该收益；Full在B3又接纳合同披露判断技能。这些是训练反馈内成果。32个受控视图直接基线全部正确，不提供额外能力证据。

## 为什么两项机制仍缺证据

- Lift：Full当前把法律条件放在已读取的inputs中，固定源前提为0；实际没有从旧常量成组提升并在另一母来源重新绑定的事件。已有当前源读取不能倒算成Lift。
- CoRev：尚无已验证的已有法律技能共同修订模式，也无跨来源实例化；新建依赖包和格式渲染链不算法律责任共同修订。
- 学习上下文覆盖14/20母来源；固定“当前最差3＋最早历史5”的选择使部分高基线MAUD来源从未进入教师上下文，不能宣称已从20来源都学到规则。原队列不因结果改选、不加来源。
- 实现问题损失了一部分候选；必须修复后再区分方法不触发、模型语义错误与真正方法不足。完整逐来源、候选与失败见[首遍审计](../reports/legal_skill_evolution_run_20261111/completed_pilot_audit.json)。

## 已完成的集中修复与当前实际任务

无在途请求、原首遍客户端已退出后，保存v11源码快照再修改：

1. 未到达分支的unknown不再提前拒绝整条程序。只传有支持的已知值，未知键缺席；只有只读字面字段访问的程序允许部分绑定，实际访问未知仍失败，禁止全字典观察/别名/动态访问/补值。
2. 没有任何前提绑定的reader不执行，避免不可观察的死读取产生失败或额外成本。
3. 未安装草稿的修订仅在记录中有唯一同ID/前版本祖先时，按原程序新建v1；保留原响应与版本关系，不把它当已有技能CoRev。8个相关失败中5个离线恢复，其他仍拒绝。
4. 教师接口显式区分trigger/history、原生答案合同及已安装技能/保留草稿；只影响以后合法提议，本次复验**不新增教师调用**。

原接口26项检查通过；补齐局部记录候选、缓存索引及正式调度/隔离后共32项相关检查通过；原始Full读取和原程序在离线实际READ/APPLY/USE链上可得OE EC/EV F1约.533/.733，未补unknown，实际访问未知的负例仍拒绝。它证明接口修复，不能当新来源或方法贡献。

**集中受影响队列已完成29/29**：10个无触发可达性的槽离线排除，其余完整版本表；4个候选有可接受mask，均不能证明专门Lift或CoRev。旧初答、旧顺序库、原提议与账本不变。复验新增237次executor、0次teacher，结束累计2622E/90T，在途0。逐臂逐批连同旧逻辑执行均≤192。

缓存查询在请求边界保留22个已结算候选和885条视图后修复；12个真实请求的离线对照结果与物理ID完全一致，查询含建索引快约7.9倍，未重算已完成前缀。新旧`repair_v12/v13`均保留。

**当前实际工作：固定128来源/8批、七系统技能学习与DEV。** 唯一入口`python -m experiments.legal_skill_evolution_formal run`已接续到formal_v2，同一学习过程，不是第二遍。原32项及新引文/失败提议回归合计37项相关检查通过，368个TRAIN/DEV原生视图输入预检复用经相同运行依赖哈希核验的结果，最大输入9468 tokens，保持8192输出上限、thinking OFF。每批16（OE4＋其他各3），原顺序；全部批初先答再更新。四主臂DEV为B0–B8，其余B0/B8，DEV不进教师或技能更新。各臂从空库开始，不导入小试技能；该入口不开TEST。当前Goal覆盖旧首阶段停止边界，完整固定实验用于检验两机制及强对照收益；小试缺证据不改记为通过，也不降低最终验收。

B0 DEV已完成，七系统空库五库等权均为.4813387；B1四主臂DEV仍为同一得分，尚无开发增益。B1自由演化、LiftOnly、CoRevOnly及Generic各接纳1个SARA技能；Full和AllPorts暂为0。训练内改对与DEV不增益分开记录，不能据技能数认定贡献。曲线和逐库指标由只读统计脚本生成，TEST未参与。

已完成有原始记录支持的前向修复：Full/B1一条法律引文的破折号/换行复制差异可唯一绑定回原文，原P、端口、法律值均不变，离线恢复编译；AllPorts另一个转述引用仍拒绝。另将已保存却未进入教师输入的失败原始提议接入后续修复上下文，所有臂一致应用。formal_v1在六臂B2更新全部结算后正常退出75，核实旧PID退出及SQLite在途0才改动绑定源码；这不是Goal暂停。随后逐字导入1482个已结算文件至formal_v2，B0–B2库、初答、更新和部分DEV视图保持，导入新增调用0、账本不重置。新客户端PID1049186/start_ticks639865782、session87795已核实；唯一有效身份记录为`artifacts/legal_skill_evolution_20261111/formal_v2/live_process.json`。原v1终态及持有文件保留，不得重启。修复只影响B3及以后，不回写旧结果。[离线复核](../reports/legal_skill_evolution_run_20261111/formal_forward_grounding_repair_review.json)与[导入收据](../reports/legal_skill_evolution_run_20261111/formal_grounding_state_import.json)保留。

B2六臂均已完成更新：Full学得一个当前输入读取的渐进税率判断器，前提常量为0；其余臂共1–2个技能，模式仍为0。该程序是普通规则获取，不计Lift或CoRev。B1实际更新阶段约19.96分钟、48E/6T，DEV与TEST另计；按B1线性外推不当作完整队列时长承诺。训练继续期间只补齐未绑定的统计、冻结TEST入口和来源迁移分析，不修改运行manifest绑定的科学代码、配置、测试或原始数据。

**接续工作已落实到可运行入口。** B8冻结及原生TEST准备为`python -m experiments.legal_skill_evolution_frozen prepare`，先验证128/8批和42个DEV点结算、哈希及无在途，再重核完整教师暴露记录，才可读取TEST评分包；随后`preflight`、`run`执行固定七系统。迁移入口`python -m experiments.legal_skill_evolution_transfer`在七系统冻结矩阵完成后使用预先冻结的Full外库掩码，无教师、无库更新、无重训练。来源沿全部真正接纳版本及编辑模式供体累积，未知不猜；实际APPLY尝试和最终答案依赖路径分开，fallback不计核心迁移。六臂B0–B2真实库/痕迹离线回归及8项相关隔离、依赖、恢复检查已通过，实际TEST与掩码调用均未开始。这些入口须接在当前训练完成后，勿与现客户端并发启动。[真实前缀回归](../reports/legal_skill_evolution_run_20261111/actual_B2_lineage_and_mask_regression.json)、[正式机制清单](../reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json)、[DEV曲线](../reports/legal_skill_evolution_run_20261111/formal_DEV_learning_curves.pdf)。

动态账本、在途和阶段结算见[运行状态](../reports/legal_skill_evolution_run_20261111/current_status.json)、[完整进度](../reports/legal_skill_evolution_run_20261111/pilot_progress.json)。
## 可复用与保全

固定方案包32项哈希、五库128/40/160母来源、280/88/352原生视图、32个受控TRAIN视图保持。Qwen3-8B原始权重、thinking OFF，教师gpt-5.6-sol/high，参数均冻结；教师温度未暴露。账本起点1893E/74T及所有失败、重复请求、旧版产物保持。

`legal_skill_guard/skill_evolution/`包含严格技能对象、隔离执行、读取/绑定、实际USE数据流、版本表选择、模式实例化、来源隔离和精确缓存。官方OE55评分文件逐字保持；格式/fixture通过不等于法律语义正确。原入口`experiments.legal_skill_evolution`的v11首遍已完成，不得再次启动旧队列。

历史暴露核验发现CNLI原TEST537正文通过旧TRAIN538进入3份教师提示，同母来源簇已复核；保留原清单，冻结前按既定hash顺序补位，候选555已完成现存记录预筛。不读取TEST标签、不用旧暴露TEST宣称盲测；历史核验范围和未完成项单列。

[执行报告](../reports/legal_skill_evolution_run_20261111/README.md) · [离线修复证据](../reports/legal_skill_evolution_run_20261111/offline_repair_regression.json) · [实际机制清单](../reports/legal_skill_evolution_run_20261111/learned_mechanism_inventory.json)。旧A/B、M1/M2否定证据、桌面确定性资产及LoRA产物保留，不恢复旧路线。
