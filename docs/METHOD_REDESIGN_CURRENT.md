# 当前证据与下一项实际工作

Goal **active、未完成**。目标、验收与边界唯一见[CURRENT_GOAL.md](CURRENT_GOAL.md)。执行目录`/home/yndx/hhy/legal-skill-redesign-20261109`、分支`research/legal-skill-evolution-20261111`；main不改。旧A/B、旧M1/M2、参数训练及历史暂停不构成行动队列。

## 实际运行与恢复

2026-11-11T19:45:54 UTC已完成原128来源/8批学习、42个DEV点、B8七系统五库各32来源TEST、注册外库技能掩码及全部结算审计。主要执行者随后核对原生统计、四项注册区间、程序/模式和费用，见[阶段复核](../reports/legal_skill_evolution_run_20261111/FIXED_STUDY_STAGE_REVIEW.md)与[主要执行者判断](../reports/legal_skill_evolution_run_20261111/primary_scientific_review.json)。没有根据TEST修改方法。

接续器1765016/start_ticks642498467、主矩阵子进程1765024/start_ticks642498475、迁移子进程1962568/start_ticks643280713和纯分析收尾器1863615/start_ticks642889676均已终止，不重启。七系统各160母来源、352原生视图，迁移各库32来源全部齐备；SQLite在途0。完成凭据位于`artifacts/legal_skill_evolution_20261111/frozen_test_v1/TEST_completed.json`、`transfer/completed.json`及`fixed_pipeline_v1/final_report_completed.json`；它们记录实验结算，不是Goal成功凭据。

恢复仍须核对真实进程和同一账本，不据旧PID、状态或会话重跑。原formal77项、freeze129项绑定保持；旧失败、原始请求、冻结程序及全部正负结果保留。原始结算证据共31066文件、907487267字节，逐项清单见[证据清单](../reports/legal_skill_evolution_run_20261111/settled_evidence_manifest.json)。

## 已完成的真实研究证据

固定128母来源、280原生TRAIN视图/臂，48次学习臂更新、42/42个固定DEV点完成。原始提议103 create、6 revise、0 Lift；接纳21 create、3 revise。原B8全部技能依赖端口及CoRev模式仍0。最终库数量：Free5、LiftOnly2、CoRevOnly3、Full4、Generic4、AllPorts3。Full B8添加Arizona/Federal and Arizona分支属于过程修补；B6三项候选完整八格为single_sufficient，两个修订处理不同任务，不是必要法律共同修订。

| B8 DEV系统 | 五库等权原生得分 |
|---|---:|
| NoSkill / Free / LiftOnly / Lift+GenericJoint | .4813387 |
| CoRevOnly | .5063387 |
| AllPorts+CoRev | .4815701 |
| Full | .5932961 |

Full对空库+.1119574，对AllPorts+.1117261；Full17个核心执行视图、4个全对，增益来自普通获取/过程修补。按原协议冻结B8，未挑B6最高DEV点。不能因臂名或分数差认领没有发生的机制。

完整TEST五库等权得分：NoSkill .4127775、Free .4139755、LiftOnly .4065275、CoRevOnly .4252775、Full .5384792、Generic .4002775、AllPorts .4261885。Full对AllPorts差+.1122908，校正98.75%区间[.0632968,.1631957]；对Generic差+.1382017，区间[.0823598,.1968819]。本固定轨迹的实际收益成立，主要来自OE和Airline；SARA略降，CNLI/MAUD不变。Full76/352程序路径、16个原生全对、276回退；不是两项专门机制证明。外库掩码160来源全不变、实际外库最终路径0，跨库收益不成立。[1120行逐来源结果](../reports/legal_skill_evolution_run_20261111/fixed_TEST_source_results.csv)按系统重复同一160来源，不算1120个独立来源。

完整TRAIN初答轨迹：Full .4668578，同案NoSkill .4427277，配对+.0241302；37个核心执行、6个新增全对，来自4个母来源；另1个SARA由对改错。AllPorts配对+.0115327。B7退化及所有回退/失败保留。图表与逐来源证据见[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)、[TRAIN轨迹](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_trajectory.json)、[DEV汇总](../reports/legal_skill_evolution_run_20261111/formal_DEV_summary.json)、[机制清单](../reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json)。

全部128来源参与初答及触发选择；每学习臂只有27个母来源的原文/反馈直接进入教师。Full为OE6/SARA8/Airline11/CNLI1/MAUD1，其他臂为OE3/SARA7/Airline15/CNLI1/MAUD1。初答覆盖不是教师获取覆盖；不另加覆盖验收门槛。

[原TRAIN前提定位](../reports/legal_skill_evolution_run_20261111/TRAIN_PRECONDITION_DECISION.md)进一步核对48次教师请求的109项原始提议：3个对照臂生成4个依赖包、6个消费技能和20个依赖端口，均已编译、完整4/8格验证，端口没有丢失；4包触发均分均无改善，1包还损害历史来源，原判据正确拒绝。它们全部是create；48个批初库均无旧依赖链，Full原始提议的依赖端口也为0。CoRev缺的是可自然连续修订的既有对象，不能将创建图或原两项独立程序修补重标为共同修订。继续需改变获取/更新协议及验证边界，超出普通接口修复；不悄悄重开原固定实验。

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

原连续账本起点1893E/74T不重置，失败、重试和物理缓存分别核算；旧100/96、teacher2或修复轮次限制不恢复。正式学习/DEV新增3304E/48T；固定预检492E/16T、集中修复237E/0T、后续获取/格式诊断15E/3T，主矩阵3141E/0T、迁移精确复用新增0，均结算。累计9082E/141T、在途0；历史失败E10/T4保留。GPU/教师发票不可见，不当作0美元。Full获取＋TEST响应消费足迹1267，对AllPorts1221，不宣称其成本优于AllPorts；物理共享缓存只收一次，不能把消费足迹相加或当独立支出。

TRAIN异常成本引用已离线补齐：28条原生视图禁网精确回放找回原3次请求的13个逐臂引用，原总账费用、全部56个初答点和评分保持，逐臂未归属请求3→0。10项统计/成本回归通过；[回放及费用证据](../reports/legal_skill_evolution_run_20261111/recovered_TRAIN_cost_references.json)属于记账修复，不算学习或机制收益。

最终OFF核对读取实际响应标志、reasoning内容和结束原因：3304次正式executor响应全部OFF、reasoning为空，其中2次截断保留；3141次冻结响应全部OFF、reasoning为空且正常stop。正常stop不当作执行或法义正确。

无损教师传输、两T并发、原生枚举预检查、CoRevOnly分发及跨版本接续均已有证据，按[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)复用，不重复有效工作。原先所有失败、旧A/B/M1M2、LoRA及确定性资产保留；不重启历史路径或强行接入已淘汰方法。

阶段交付以开发分支发布及独立取回核验收据为准。当前明确结论为“固定实验和实际分数收益成立，本研究未证实两项专门贡献”，Goal未完成。继续追求原双贡献的下一步是针对学习对象与自然依赖更新信号作一次明确研究调整决定；现有接口修补或同类加量不足以支持它。不重跑矩阵、不扩源、扫参数或按TEST修方法，不把报告交付认作Goal成功，也不自动进入论文；没有新增机械调用上限或逐轮授权要求。
