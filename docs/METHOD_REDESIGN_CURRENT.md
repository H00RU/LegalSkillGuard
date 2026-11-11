# 当前证据与下一项实际工作

Goal **active、未完成**。唯一目标和验收见[CURRENT_GOAL.md](CURRENT_GOAL.md)。执行目录 `/home/yndx/hhy/legal-skill-redesign-20261109`，分支 `research/legal-skill-evolution-20261111`；main不修改。历史暂停、旧A/B/M1/M2及参数训练路径不再构成动作队列。

## 当前实测

固定128母来源/8批、七系统外部技能学习已完成**B1–B3的48来源初答及18次学习臂更新、对应DEV**，当前B4初答。每批16（OE4、其余各3），全部七臂初答完成才更新；教师只看已见TRAIN，模型不更新参数。TEST仍封存。

三批共105个原生视图/臂，七系统批初新来源主路径正确均为0，当前与同来源NoSkill的差值均为0；反馈内改对另记。B3批初五库等权均为.4167478，各批案情不同，不能据批间分数变化判断学习收益。[逐来源配对轨迹](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_trajectory.json)、[训练图](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_learning_trajectory.pdf)分开显示任务得分、同案NoSkill差值、库规模、回退和排除DEV后的请求使用量。共享缓存不重复计实际支出，各臂响应使用量不能相加冒充独立费用。

B3末技能数：FreeEvolution3、LiftOnly2、CoRevOnly2、Full2、Lift+GenericJoint2、AllPorts+CoRev1。39项教师原始操作全为create，35项编译、12项最终接纳；专门Lift与已有技能共同修订提议均为0，全部CoRev模式0。Full的两个SARA程序均把法源条件作为当前读取的inputs，固定前提0，属于普通参数化获取，不能倒算Lift。版本表选择器为所有臂共用，不能认领通用枚举选择的增量。[正式机制清单](../reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json)。

B0七系统、B1–B3四主臂DEV五库等权均为.4813387，尚无增益。B2 FreeEvolution/LiftOnly/CoRevOnly各1个DEV视图由核心技能答对，但基线原本正确；Full核心执行0。B3四主臂各1个DEV视图核心答对，仍是基线原本正确的题，当前19/42个注册DEV点完成，不外推未来点。[DEV统计](../reports/legal_skill_evolution_run_20261111/formal_DEV_summary.json)、[DEV曲线](../reports/legal_skill_evolution_run_20261111/formal_DEV_learning_curves.pdf)。

## 当前进程与本次工程决定

唯一入口 `python -m experiments.legal_skill_evolution_formal run`，当前配置 `configs/legal_skill_evolution_formal_v3_20261111.json`，PID1166485/start_ticks640286217、session42899；实际身份记录为 `artifacts/legal_skill_evolution_20261111/formal_v3/live_process.json`。恢复先核实该PID和SQLite在途，不只看本文件。formal_v1/v2均已终态并保留持有文件，不能重启。Goal始终active，工程请求边界持有不是用户暂停。

首批更新实测19.96分钟、48E/6T，其中教师累计965.99秒，约占81%；DEV/TEST另计。为减少串行等待，**B4起同一批六臂独立教师提议最多两路并发，执行模型及候选验证仍串行**。教师gpt-5.6-sol/high、Qwen3-8B/thinking OFF及采样参数不变；同批初库、最差3当前＋最早5历史、共享3候选/192逻辑执行均不变。2是并发数，不是教师累计调用上限。不增加探测调用；真实并发与耗时将由正常B4提议验证，尚不宣称实测提速。

隔离目录及接入后42项回归通过，覆盖两T记账、E互斥、跨run隔离、失败排空/停止未发送、已完成提议恢复不重发。12个新鲜fixture输入及6个真实B3缓存上下文的新旧模型提议输入字节一致；与原请求逐值、类型、schema和源文本核对也一致。原请求与缓存重读存在JSON键序差异，该差异在旧代码中同样存在，已单列，未放松真实响应缓存的逐字匹配。[工程复核](../reports/legal_skill_evolution_run_20261111/formal_teacher_parallel_review.json)、[真实输入核对](../reports/legal_skill_evolution_run_20261111/actual_teacher_prefetch_payload_parity.json)。

六臂B3更新全结算、旧PID退出75、在途0后才接入；逐字导入2723个已结算文件，B0–B3库/初答/更新及部分DEV缓存保持，新模型调用0、账本不重置。原368视图预检在运行/原生编解码/worker/wire/数据及模型配置哈希一致的核验后复用，最大输入9468 tokens，输出8192不变。[导入收据](../reports/legal_skill_evolution_run_20261111/formal_teacher_overlap_state_import.json)。

## 保全和下一步

同一SQLite账本保留1893E/74T起点及全部失败、重试与旧输出；旧96/100、teacher2或修复轮次上限不恢复。[动态状态](../reports/legal_skill_evolution_run_20261111/current_status.json)、[阶段成本](../reports/legal_skill_evolution_run_20261111/stage_costs.json)与原始记录分开保存；GPU/教师实际现金发票不可见，不能把本地增量API为0说成整个实验免费。

固定20来源首遍16更新和29项受影响集中复验均已完成，分别新增492E/16T、237E/0T。旧结果、失败及两机制未触发的否定证据保留，不重做旧构造实验、不导入小试库。unknown未到达分支、无绑定死读取、唯一未安装草稿及引文转录/失败原程序可见性修复的原始回归见[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)及各修复收据。

下一项实际工作：继续现客户端余五批，使用正常B4提议检查两教师并发及连续记账，保持全部失败与回退分母。之后按已实现入口 `python -m experiments.legal_skill_evolution_frozen prepare` 核验128/8批和42个DEV点、无在途与完整教师暴露，才读取TEST；再执行 `preflight`、`run` 和 `python -m experiments.legal_skill_evolution_transfer`。迁移掩码与来源版本追踪已在B0–B2六臂真实库/痕迹上离线核验，8项隔离/恢复检查通过；这些不是迁移效果。

CNLI原TEST537通过旧TRAIN538暴露，原清单保留，按预定hash补位555；不改TRAIN/DEV，不用旧暴露来源宣称盲测。冻结及迁移入口不加教师、不更新库、不改测试追分。只有完整实验、相对强对照实际收益及两项独立贡献均被支持才完成Goal；当前这些条件尚未满足，不自动进入论文。
