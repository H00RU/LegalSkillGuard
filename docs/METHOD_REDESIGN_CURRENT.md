# 当前证据与下一项实际工作

Goal **active、未完成**。唯一目标和验收见[CURRENT_GOAL.md](CURRENT_GOAL.md)。执行目录 `/home/yndx/hhy/legal-skill-redesign-20261109`，分支 `research/legal-skill-evolution-20261111`；main不修改。历史暂停、旧A/B/M1/M2及参数训练路径不再构成动作队列。

## 当前实测

固定128母来源/8批、七系统外部技能学习已完成**前7批112来源初答、42次学习臂更新及对应DEV**，当前B8初答。每批16（OE4、其余各3），全部七臂初答完成才更新；教师只看已见TRAIN，模型不更新参数。TEST仍封存。

前四批共140个原生视图/臂，七系统批初新来源主路径正确均为0。B5 Full首次在一个新航空来源用B4旧库主路径答对，同案NoSkill错；这是更新前实际复用，其他臂该批核心正确仍0。反馈内改对另记。B3批初五库等权均为.4167478，各批案情不同，不能据批间分数变化判断学习收益。[逐来源配对轨迹](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_trajectory.json)、[训练图](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_learning_trajectory.pdf)分开显示任务得分、同案NoSkill差值、库规模、回退和排除DEV后的请求使用量。共享缓存不重复计实际支出，各臂响应使用量不能相加冒充独立费用。

B6末技能数：FreeEvolution4、LiftOnly2、CoRevOnly2、Full4、Lift+GenericJoint3、AllPorts+CoRev2。累计提议81次create、2次revise、0次Lift，全部CoRev模式0。Full两项SARA程序从获取时已直接读取参数；后续虽有固定法源前提，仍无专门Lift转换。所有当前库技能依赖输入端口数均0；B6两个旧程序修订已完成8格，分类single_sufficient，并非联合必要事件。版本表选择器为所有臂共用，不能认领通用枚举选择的增量。[正式机制清单](../reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json)。

B0七系统、B1–B3四主臂DEV五库等权均为.4813387。**B4 Full为.5313387，比其B0高.0500**，航空库从0/8变为2/8；另外三主臂B4仍为.4813387。Full B4共有3个核心正确DEV视图，其中1个SARA题基线本来正确，新增2个航空题由行李费程序实际执行。其他四库得分不变；两个强对照的下一注册DEV点为B8，不能据此宣布优于强对照。B5 Full为.5446176，OE原生F1均分从.1983604到.2647547，航空仍.25、其他三库不变；完全正确的核心视图仍3个。其他三主臂B5仍.4813387。截至B6为31/42个注册DEV点完成；部分F1改善与新增全对分开，不计专门Lift/CoRev贡献。[DEV统计](../reports/legal_skill_evolution_run_20261111/formal_DEV_summary.json)、[DEV曲线](../reports/legal_skill_evolution_run_20261111/formal_DEV_learning_curves.pdf)。

逐来源覆盖已补齐，并与同一SQLite中的30个已结算教师响应逐项核对。前5批每学习臂直接向教师提供18个独立来源；Full为OE3、SARA5、Airline8、CNLI1、MAUD1，其他臂SARA4、Airline9，其余相同。全部80来源的初答分数参与最差触发组选择，只有所选cohort进入教师原文/反馈。两者不等同；不因此新增覆盖阈值或改变固定策略。逐来源的初答、教师trigger/history角色与当前技能声明引文分别保留在[机制清单](../reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json)的source_level_learning_coverage，未处理来源保持unknown。

B6已结算：Full固定DEV五库均分.5999947（OE .4166400、Airline .375，其他三库不变），完全正确的核心视图4个；其他三主臂仍.4813387。B6训练初答使用B5末库，同16来源五库等权均分.5051587，相对同来源NoSkill差+.1243633；这是不同新案的实际复用轨迹，不能直接拿训练与DEV分数相减。累计81次create、2次revise、0次Lift，所有当前库的skill依赖输入端口数均0。Full的三项候选已完成8格，选择mask6（两个旧程序修订），分类为single_sufficient；实际是航空与豁免任务的独立修复，不能作为需要法律依赖共同修订的证据，模式数仍0。当前证据证明普通程序获取/修订的收益，未证明两项专门机制。

技能生成频率固定为每16来源初答后，各学习臂1次教师，共6次/批；正式7批42次，8批计划48次，NoSkill不调教师。每次最多3个候选包、每包最多3项编辑，实际可不接纳。教师直接读取最差3个新来源＋最多5个固定历史来源，另有当前库与旧编辑；不是直接获得本批全部16个原文/反馈。前5批每臂18/80的直接覆盖是当前采样设计局限，与16案评分用于选择的口径分开，不中途更改策略或加新案例追分。库参数与两模型权重均不做梯度更新。

B7更新前Full有35个原生视图：12个核心执行完成、0个核心全对、23个回退，未发生整视图调用中断。五库等权得分.4305556，同案NoSkill .5274116，差-.0968561；损失来自OE与SARA。OE程序读到未覆盖的Federal and Oregon/Federal and Arizona后仍正常返回空claim列表，属于语义覆盖错误，执行成功不能等同正确。B7六臂提议均未获接纳，库大小保持，所有库skill依赖端口和CoRev模式仍0；累计91 create、4 revise、0 Lift，接纳17 create、2 revise。35/42个固定DEV点已完成，Full B7仍.5999947，其他三主臂仍.4813387。错误并不稀缺，但独立程序修补不能替代已有依赖技能的必要共同修订；不人为拆链或把错误答案改记为回退。

## 当前进程与本次工程决定

唯一入口 `python -m experiments.legal_skill_evolution_formal run`，当前配置 `configs/legal_skill_evolution_formal_v5_20261111.json`，PID1382062/start_ticks641058649、session38824；实际身份记录为 `artifacts/legal_skill_evolution_20261111/formal_v5/live_process.json`。恢复先核实该PID和SQLite在途，不只看本文件。formal_v1/v2均已终态并保留持有文件，v3在B5教师输入传输检查失败后退出1；v4为修复CoRevOnly分发遗漏已在请求边界退出75；四个旧命名空间均不能重启。Goal始终active，工程请求边界持有不是用户暂停。

首批更新实测19.96分钟、48E/6T，其中教师累计965.99秒，约占81%；DEV/TEST另计。为减少串行等待，**B4起同一批六臂独立教师提议最多两路并发，执行模型及候选验证仍串行**。教师gpt-5.6-sol/high、Qwen3-8B/thinking OFF及采样参数不变；同批初库、最差3当前＋最早5历史、共享3候选/192逻辑执行均不变。2是并发数，不是教师累计调用上限。不增加探测调用；正常B4六次提议均已完成，CLI峰值并发2，六次耗时之和1125.23秒、阶段墙钟565.40秒，观察到的区间重叠因子1.9904，阶段内E请求0；不是另跑串行对照的因果加速估计，也不计方法收益。[实际并发](../reports/legal_skill_evolution_run_20261111/actual_teacher_overlap.json)。

此前v2→v3双教师调度接入时，隔离目录及接入后42项回归通过，覆盖两T记账、E互斥、跨run隔离、失败排空/停止未发送、已完成提议恢复不重发。12个新鲜fixture输入及6个真实B3缓存上下文的新旧模型提议输入字节一致；与原请求逐值、类型、schema和源文本核对也一致。原请求与缓存重读存在JSON键序差异，该差异在旧代码中同样存在，已单列，未放松真实响应缓存的逐字匹配。[工程复核](../reports/legal_skill_evolution_run_20261111/formal_teacher_parallel_review.json)、[真实输入核对](../reports/legal_skill_evolution_run_20261111/actual_teacher_prefetch_payload_parity.json)。

六臂B3更新全结算、旧PID退出75、在途0后才接入；逐字导入2723个已结算文件，B0–B3库/初答/更新及部分DEV缓存保持，新模型调用0、账本不重置。原368视图预检在运行/原生编解码/worker/wire/数据及模型配置哈希一致的核验后复用，最大输入9468 tokens，输出8192不变。[导入收据](../reports/legal_skill_evolution_run_20261111/formal_teacher_overlap_state_import.json)。

B5全部七臂80来源初答已完成。FreeEvolution完整教师输入1082126字符超过CLI固定1048576字符上限，本地拒绝前未新增其物理请求；并行LiftOnly的1个提议已完成并保留。当前统一使用**可逆的重复JSON值引用编码**，六个真实B5输入还原后每个值、类型、键序和原文字符串与旧输入一致，完整输入降至36.7万–50.9万字符；未删除原文、反馈、旧程序或版本结果，六臂共同使用，模型配置不变。[传输回归](../reports/legal_skill_evolution_run_20261111/actual_B5_teacher_transport_regression.json)。

v3真实退出、在途0和原绑定不变核实后，4315个已结算文件原样接至v4；23个DEV聚合由复制的精确视图缓存恢复并与原文件逐字一致，新增模型调用0。保留B1–B4更新、B5全部初答和成功LiftOnly提议，其余5个教师已正常完成，B5六臂候选/语义验证及DEV均已结算。原生枚举提前检查同时接入全部臂，384个受影响TRAIN读取回放保持答案/主路径/回退/终端/检索，可省690次逻辑读取；未知程序及中间依赖仍走原执行。隔离52项、接入及冻结恢复共60项检查通过。[工程复核](../reports/legal_skill_evolution_run_20261111/formal_native_enum_review.json)、[状态接续](../reports/legal_skill_evolution_run_20261111/formal_native_enum_state_import.json)。这些工程收益不计Lift/CoRev贡献。v4 manifest绑定的两份离线回归JSON保持冻结，运行中不重写。

方法与消融代码复核发现CoRevOnly遗漏了`patterns.learn`与`patterns.candidates`两条M2分发，已补齐为与Full相同的模式学习/伴随生成路径，仍禁用专门Lift。修复前两个功能回归均只在CoRevOnly失败，修复后54项隔离检查、接入及冻结恢复共62项通过。30个真实已结算上下文的教师输入前后字节一致，CoRevOnly前5批接受的均为单项新建，调用补齐后库/模式/分数不变；此缺陷不解释所有臂此前零机制事件。未重新评分或补调教师。[真实前缀核对](../reports/legal_skill_evolution_run_20261111/actual_corevision_arm_routing_regression.json)、[接入复核](../reports/legal_skill_evolution_run_20261111/formal_corevision_arm_review.json)。

v4在途结算、原冻结文件不变核实后，5327个文件逐字接至v5，保留B1–B5、27个DEV点和B6已完成初答（六臂各16、AllPorts10）。初答运行时、读取/教师模型配置、数据和预算不变，检查与导入新增模型调用0；账本在接续时为4922E/120T，未重置。当前客户端已完成B6全部初答并进入正常教师更新。[状态接续](../reports/legal_skill_evolution_run_20261111/formal_corevision_arm_state_import.json)。新绑定的路由回归JSON及before/after测试文本保持冻结，不在运行中重写。

## 保全和下一步

同一SQLite账本保留1893E/74T起点及全部失败、重试与旧输出；旧96/100、teacher2或修复轮次上限不恢复。[动态状态](../reports/legal_skill_evolution_run_20261111/current_status.json)、[阶段成本](../reports/legal_skill_evolution_run_20261111/stage_costs.json)与原始记录分开保存；GPU/教师实际现金发票不可见，不能把本地增量API为0说成整个实验免费。

固定20来源首遍16更新和29项受影响集中复验均已完成，分别新增492E/16T、237E/0T。旧结果、失败及两机制未触发的否定证据保留，不重做旧构造实验、不导入小试库。unknown未到达分支、无绑定死读取、唯一未安装草稿及引文转录/失败原程序可见性修复的原始回归见[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)及各修复收据。

下一项实际工作：继续现客户端B8初答、更新与固定DEV；不增加探测或重发成功请求。保持全部失败与回退分母，正常队列外不补来源或调参数。之后按已实现入口 `python -m experiments.legal_skill_evolution_frozen prepare` 核验128/8批和42个DEV点、无在途与完整教师暴露，才读取TEST；再执行 `preflight`、`run` 和 `python -m experiments.legal_skill_evolution_transfer`。迁移掩码与来源版本追踪已在B0–B2六臂真实库/痕迹上离线核验，8项隔离/恢复检查通过；这些不是迁移效果。

CNLI原TEST537通过旧TRAIN538暴露，原清单保留，按预定hash补位555；不改TRAIN/DEV，不用旧暴露来源宣称盲测。冻结及迁移入口不加教师、不更新库、不改测试追分。只有完整实验、相对强对照实际收益及两项独立贡献均被支持才完成Goal；当前这些条件尚未满足，不自动进入论文。
