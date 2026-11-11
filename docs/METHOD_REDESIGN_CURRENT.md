# 当前证据与下一项实际工作

Goal **active、未完成**。唯一目标和验收见[CURRENT_GOAL.md](CURRENT_GOAL.md)。执行目录 `/home/yndx/hhy/legal-skill-redesign-20261109`，分支 `research/legal-skill-evolution-20261111`；main不修改。历史暂停、旧A/B/M1/M2及参数训练路径不再构成动作队列。

## 当前实测

固定128母来源/8批、七系统外部技能学习已完成**前5批80来源初答、前4批24次学习臂更新及对应DEV**，当前接续B5剩余更新。每批16（OE4、其余各3），全部七臂初答完成才更新；教师只看已见TRAIN，模型不更新参数。TEST仍封存。

前四批共140个原生视图/臂，七系统批初新来源主路径正确均为0。B5 Full首次在一个新航空来源用B4旧库主路径答对，同案NoSkill错；这是更新前实际复用，其他臂该批核心正确仍0。反馈内改对另记。B3批初五库等权均为.4167478，各批案情不同，不能据批间分数变化判断学习收益。[逐来源配对轨迹](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_trajectory.json)、[训练图](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_learning_trajectory.pdf)分开显示任务得分、同案NoSkill差值、库规模、回退和排除DEV后的请求使用量。共享缓存不重复计实际支出，各臂响应使用量不能相加冒充独立费用。

B4末技能数：FreeEvolution3、LiftOnly2、CoRevOnly2、Full3、Lift+GenericJoint2、AllPorts+CoRev1。56项教师原始操作全为create，52项编译、13项最终接纳；专门Lift与已有技能共同修订提议均为0，全部CoRev模式0。Full的两个SARA程序均把法源条件作为当前读取的inputs，固定前提0；B4新增有8项固定前提的行李费程序。新建和参数化获取均不能倒算Lift。版本表选择器为所有臂共用，不能认领通用枚举选择的增量。[正式机制清单](../reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json)。

B0七系统、B1–B3四主臂DEV五库等权均为.4813387。**B4 Full为.5313387，比其B0高.0500**，航空库从0/8变为2/8；另外三主臂B4仍为.4813387。Full B4共有3个核心正确DEV视图，其中1个SARA题基线本来正确，新增2个航空题由行李费程序实际执行。其他四库得分不变；两个强对照的下一注册DEV点为B8，不能据此宣布优于强对照。当前23/42个注册DEV点完成；这是普通技能跨来源获取/执行的实证，尚不是专门Lift或CoRev的独立贡献。[DEV统计](../reports/legal_skill_evolution_run_20261111/formal_DEV_summary.json)、[DEV曲线](../reports/legal_skill_evolution_run_20261111/formal_DEV_learning_curves.pdf)。

## 当前进程与本次工程决定

唯一入口 `python -m experiments.legal_skill_evolution_formal run`，当前配置 `configs/legal_skill_evolution_formal_v4_20261111.json`，PID1300566/start_ticks640783818、session97491；实际身份记录为 `artifacts/legal_skill_evolution_20261111/formal_v4/live_process.json`。恢复先核实该PID和SQLite在途，不只看本文件。formal_v1/v2均已终态并保留持有文件，v3在B5教师输入传输检查失败后退出1；三个旧命名空间均不能重启。Goal始终active，工程请求边界持有不是用户暂停。

首批更新实测19.96分钟、48E/6T，其中教师累计965.99秒，约占81%；DEV/TEST另计。为减少串行等待，**B4起同一批六臂独立教师提议最多两路并发，执行模型及候选验证仍串行**。教师gpt-5.6-sol/high、Qwen3-8B/thinking OFF及采样参数不变；同批初库、最差3当前＋最早5历史、共享3候选/192逻辑执行均不变。2是并发数，不是教师累计调用上限。不增加探测调用；正常B4六次提议均已完成，CLI峰值并发2，六次耗时之和1125.23秒、阶段墙钟565.40秒，观察到的区间重叠因子1.9904，阶段内E请求0；不是另跑串行对照的因果加速估计，也不计方法收益。[实际并发](../reports/legal_skill_evolution_run_20261111/actual_teacher_overlap.json)。

此前v2→v3双教师调度接入时，隔离目录及接入后42项回归通过，覆盖两T记账、E互斥、跨run隔离、失败排空/停止未发送、已完成提议恢复不重发。12个新鲜fixture输入及6个真实B3缓存上下文的新旧模型提议输入字节一致；与原请求逐值、类型、schema和源文本核对也一致。原请求与缓存重读存在JSON键序差异，该差异在旧代码中同样存在，已单列，未放松真实响应缓存的逐字匹配。[工程复核](../reports/legal_skill_evolution_run_20261111/formal_teacher_parallel_review.json)、[真实输入核对](../reports/legal_skill_evolution_run_20261111/actual_teacher_prefetch_payload_parity.json)。

六臂B3更新全结算、旧PID退出75、在途0后才接入；逐字导入2723个已结算文件，B0–B3库/初答/更新及部分DEV缓存保持，新模型调用0、账本不重置。原368视图预检在运行/原生编解码/worker/wire/数据及模型配置哈希一致的核验后复用，最大输入9468 tokens，输出8192不变。[导入收据](../reports/legal_skill_evolution_run_20261111/formal_teacher_overlap_state_import.json)。

B5全部七臂80来源初答已完成。FreeEvolution完整教师输入1082126字符超过CLI固定1048576字符上限，本地拒绝前未新增其物理请求；并行LiftOnly的1个提议已完成并保留。当前统一使用**可逆的重复JSON值引用编码**，六个真实B5输入还原后每个值、类型、键序和原文字符串与旧输入一致，完整输入降至36.7万–50.9万字符；未删除原文、反馈、旧程序或版本结果，六臂共同使用，模型配置不变。[传输回归](../reports/legal_skill_evolution_run_20261111/actual_B5_teacher_transport_regression.json)。

v3真实退出、在途0和原绑定不变核实后，4315个已结算文件原样接至v4；23个DEV聚合由复制的精确视图缓存恢复并与原文件逐字一致，新增模型调用0。保留B1–B4更新、B5全部初答和成功LiftOnly提议，仅续余5个教师。原生枚举提前检查同时接入全部臂，384个受影响TRAIN读取回放保持答案/主路径/回退/终端/检索，可省690次逻辑读取；未知程序及中间依赖仍走原执行。隔离52项、接入及冻结恢复共60项检查通过。[工程复核](../reports/legal_skill_evolution_run_20261111/formal_native_enum_review.json)、[状态接续](../reports/legal_skill_evolution_run_20261111/formal_native_enum_state_import.json)。这些工程收益不计Lift/CoRev贡献。v4 manifest绑定的两份离线回归JSON保持冻结，运行中不重写。

## 保全和下一步

同一SQLite账本保留1893E/74T起点及全部失败、重试与旧输出；旧96/100、teacher2或修复轮次上限不恢复。[动态状态](../reports/legal_skill_evolution_run_20261111/current_status.json)、[阶段成本](../reports/legal_skill_evolution_run_20261111/stage_costs.json)与原始记录分开保存；GPU/教师实际现金发票不可见，不能把本地增量API为0说成整个实验免费。

固定20来源首遍16更新和29项受影响集中复验均已完成，分别新增492E/16T、237E/0T。旧结果、失败及两机制未触发的否定证据保留，不重做旧构造实验、不导入小试库。unknown未到达分支、无绑定死读取、唯一未安装草稿及引文转录/失败原程序可见性修复的原始回归见[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)及各修复收据。

下一项实际工作：继续现客户端B5剩余教师/候选更新和DEV，再执行B6–B8；新传输已有正常结构化教师提议返回，继续原定候选执行验证，不增加探测或重发成功请求。保持全部失败与回退分母，正常队列外不补来源或调参数。之后按已实现入口 `python -m experiments.legal_skill_evolution_frozen prepare` 核验128/8批和42个DEV点、无在途与完整教师暴露，才读取TEST；再执行 `preflight`、`run` 和 `python -m experiments.legal_skill_evolution_transfer`。迁移掩码与来源版本追踪已在B0–B2六臂真实库/痕迹上离线核验，8项隔离/恢复检查通过；这些不是迁移效果。

CNLI原TEST537通过旧TRAIN538暴露，原清单保留，按预定hash补位555；不改TRAIN/DEV，不用旧暴露来源宣称盲测。冻结及迁移入口不加教师、不更新库、不改测试追分。只有完整实验、相对强对照实际收益及两项独立贡献均被支持才完成Goal；当前这些条件尚未满足，不自动进入论文。
