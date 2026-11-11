# 当前证据与下一项实际工作

Goal **active、未完成**。目标、验收与边界唯一见[CURRENT_GOAL.md](CURRENT_GOAL.md)。执行目录`/home/yndx/hhy/legal-skill-redesign-20261109`、分支`research/legal-skill-evolution-20261111`；main不改。旧A/B、旧M1/M2、参数训练及历史暂停不构成行动队列。

## 实际运行与恢复

检查时间：2026-11-11T19:05:38.917967+00:00。原128来源/8批正式学习和42个DEV点均已结算；B8、资格审查及输入容量检查通过。当前阶段`frozen_TEST`，只生成原冻结矩阵及随后已注册迁移；不使用这些预测指导修复。

原接续器PID1765016/start_ticks642498467，session79159；当前子进程PID1765024/start_ticks642498475，入口`python -m experiments.legal_skill_evolution_frozen run`、配置`configs/legal_skill_evolution_frozen_v1_20261111.json`。实时唯一入口`artifacts/legal_skill_evolution_20261111/fixed_pipeline_v1/status.json`。已提交父来源检查点计数（仅数量，未读部分TEST得分）：{"NoSkill": 160, "FreeEvolution": 160, "LiftOnly": 160, "CoRevOnly": 160, "Full": 160, "Lift+GenericJoint": 85, "AllPorts+CoRev": 0}，每臂目标160。

纯分析收尾器PID1863615/start_ticks642889676、session7804，入口`/tmp/lsg_finalize_fixed_evidence_20261112.py`；实时状态`fixed_pipeline_v1/final_report_status.json`。它等待上述实际接续器退出，并核对TEST/迁移完成凭据、绑定和在途0后，生成固定研究审计、成本和结算证据。该入口新增模型0、不发布、不改Goal状态；完成后由主要执行者科学复核。

恢复必须核对真实PID、start_ticks、SQLite在途及完成凭据，不能只读本页或重起旧任务。旧formal PID1382062已退出0；旧controller1487538/child1572906已在工程边界退出75。旧session72926、5779、91629均不恢复。原formal77项、freeze129项绑定反复核实未变；运行中不可重写绑定的源码、配置、测试、数据或回归JSON。

## 已完成的真实研究证据

固定128母来源、280原生TRAIN视图/臂，48次学习臂更新、42/42个固定DEV点完成。原始提议103 create、6 revise、0 Lift；接纳21 create、3 revise。原B8全部技能依赖端口及CoRev模式仍0。最终库数量：Free5、LiftOnly2、CoRevOnly3、Full4、Generic4、AllPorts3。Full B8添加Arizona/Federal and Arizona分支属于过程修补；B6三项候选完整八格为single_sufficient，两个修订处理不同任务，不是必要法律共同修订。

| B8 DEV系统 | 五库等权原生得分 |
|---|---:|
| NoSkill / Free / LiftOnly / Lift+GenericJoint | .4813387 |
| CoRevOnly | .5063387 |
| AllPorts+CoRev | .4815701 |
| Full | .5932961 |

Full对空库+.1119574，对AllPorts+.1117261；Full17个核心执行视图、4个全对，增益来自普通获取/过程修补。按原协议冻结B8，未挑B6最高DEV点。不能因臂名或分数差认领没有发生的机制。

完整TRAIN初答轨迹：Full .4668578，同案NoSkill .4427277，配对+.0241302；37个核心执行、6个新增全对，来自4个母来源；另1个SARA由对改错。AllPorts配对+.0115327。B7退化及所有回退/失败保留。图表与逐来源证据见[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)、[TRAIN轨迹](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_trajectory.json)、[DEV汇总](../reports/legal_skill_evolution_run_20261111/formal_DEV_summary.json)、[机制清单](../reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json)。

全部128来源参与初答及触发选择；每学习臂只有27个母来源的原文/反馈直接进入教师。Full为OE6/SARA8/Airline11/CNLI1/MAUD1，其他臂为OE3/SARA7/Airline15/CNLI1/MAUD1。初答覆盖不是教师获取覆盖；不另加覆盖验收门槛。

## 根因定位与已实施修复

隔离工程树`/media/sangfor/vdb/legal-skill-runtime/engineering/lift-corev-activation-20261112`、分支`repair/lift-corev-activation-20261112`，不向原冻结目录注入科学改动。最新公开实现及逐字核验见`reports/legal_skill_evolution_run_20261111/activation_publication_manifest.json`与对应verified收据。

1. Lift原先只显示候选，且教师必须重写整份Skill再被要求P不变。现有小型reader提议、确定性编译及真实失败视图排队，保留原P/输入输出/旧版本，仍按原完整回放准入。
2. 3个固定教师任务已完成，累计15E/3T全结算。真实航空Lift新旧尺寸相同、得分前后0/1，未接纳；未补入缺失国际航线分支。Full/Free各自从空库获取§152(a)→§152(b)(1)两技能，均在原§152题0→1；属于创建，不是旧技能共同修订。Free只漏函数壳，保留body AST适配后复用原响应，教师未重调。
3. Full另在§151(c)错用§152终端而碰巧得分1，现已通过“明确最终命题声明＋硬编码current-question读取绑定”的保守检查修复。禁网、只读账本、逐字节缓存回放验证两臂四条记录：§151误用改回退，真正§152核心保持，原生分数不变、新增模型0。没有明确声明/多条款/父子范围时unknown；不是完整语义验证，更不是创新收益。
4. 当前错误视图目标提示定位64份真实教师上下文中的216个未满分/未解视图；Lift只从这些视图的实际尝试排队。八个历史排队不变；提示的真实模型收益尚未验证。当前71项相关回归通过。严格删除case-reader法源的原型已退出路径；完整原文、given中间结论及原准入规则保留。

完整代码、原始响应、作用域回归和费用见[修复报告](../reports/legal_skill_evolution_run_20261111/ACTIVATION_REPAIR_20261112.md)、[范围回归](../reports/legal_skill_evolution_run_20261111/claim_scope_actual_response_regression.json)、[修复物理账本摘要](../reports/legal_skill_evolution_run_20261111/activation_repair_summary.json)。工程修复、缓存回放、回退正确及少量主路径成功不能替代双贡献验收。

## 现有学习信号的边界

[TRAIN信号审计](../reports/legal_skill_evolution_run_20261111/training_signal_audit.json)确认：原32个受控直接基线32/32正确；MAUD24个受控角色条件均给定True。仅修已正确控题不满足原严格提分准入，不能借此证明角色归属改善。OE32及Airline24案分别共用同一法条/政策正文；适用记录仍可变化，不把这当作“所有Lift不可能”的证明。SARA有8个正文族、24个精确查询条款各1次。CNLI/MAUD有变动合同/摘录，但原生任务无额外case-facts字段，完整问卷的Boolean READ→标签不等于学得法义计算。

早期小试16份去重教师响应已有13项合同修订。Full小试B3确曾接纳NDA许可程序；AllPorts/Generic知识依赖包也已实际执行，但在MAUD447上分别6/7→5/7、6/7→6/7，未修复真正错误的负面契约疫情例外。此处已完成的等价验证和负证据不重跑。源获取/更新对象、模型字段误读、准入信号和语义核验缺失需要分开，不再把所有缺口归为schema。

## 资源、保全和下一步

原连续账本起点1893E/74T不重置，失败、重试和物理缓存分别核算；旧100/96、teacher2或修复轮次限制不恢复。正式学习/DEV新增3304E/48T；固定预检492E/16T、集中修复237E/0T、后续获取/格式诊断15E/3T已结算，冻结矩阵单列且禁教师。最新累计和在途只读同一SQLite及[动态状态](../reports/legal_skill_evolution_run_20261111/pilot_progress.json)，不硬覆盖成本文旧数字。GPU/教师发票不可见，不当作0美元。冻结矩阵和迁移的实际物理成本与各臂响应消费足迹分开，不把缓存首访差异当方法收益。

无损教师传输、两T并发、原生枚举预检查、CoRevOnly分发及跨版本接续均已有证据，按[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)复用，不重复有效工作。原先所有失败、旧A/B/M1M2、LoRA及确定性资产保留；不重启历史路径或强行接入已淘汰方法。

下一项实际工作：让现存矩阵、注册迁移和纯分析收尾器完整结算，再由主要执行者核对原生统计、四项预注册区间、逐来源、费用及两项独立贡献。目前未发现已验证的自然共同修订见证，不为非零计数追加同类小试；这是有限研究判断，不是新机械调用上限。不得根据TEST调方法。完整矩阵不能补出训练期没发生的机制，双贡献不足则如实报告未完成及具体研究调整需求；不自动完成Goal、不进入论文、不无限换方向。
