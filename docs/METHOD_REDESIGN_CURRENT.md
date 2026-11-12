# 当前证据与下一项实际工作

Goal **active、未完成**；用户已Resume并明确授权同Goal内协议调整，原范围阻断已解除，旧计数不再适用。目标、验收与边界唯一见[CURRENT_GOAL.md](CURRENT_GOAL.md)。执行目录`/home/yndx/hhy/legal-skill-redesign-20261109`、分支`research/legal-skill-evolution-20261111`；main不改。旧A/B、旧M1/M2、参数训练及历史暂停不构成行动队列。

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

原连续账本起点1893E/74T不重置，失败、重试和物理缓存分别核算；旧100/96、teacher2或修复轮次限制不恢复。正式学习/DEV新增3304E/48T；固定预检492E/16T、集中修复237E/0T、后续获取/格式诊断15E/3T，主矩阵3141E/0T、迁移精确复用新增0，均结算。原固定研究累计9082E/141T、在途0（后续新增见当前有限验证段）；历史失败E10/T4保留。GPU/教师发票不可见，不当作0美元。Full获取＋TEST响应消费足迹1267，对AllPorts1221，不宣称其成本优于AllPorts；物理共享缓存只收一次，不能把消费足迹相加或当独立支出。

TRAIN异常成本引用已离线补齐：28条原生视图禁网精确回放找回原3次请求的13个逐臂引用，原总账费用、全部56个初答点和评分保持，逐臂未归属请求3→0。10项统计/成本回归通过；[回放及费用证据](../reports/legal_skill_evolution_run_20261111/recovered_TRAIN_cost_references.json)属于记账修复，不算学习或机制收益。

最终OFF核对读取实际响应标志、reasoning内容和结束原因：3304次正式executor响应全部OFF、reasoning为空，其中2次截断保留；3141次冻结响应全部OFF、reasoning为空且正常stop。正常stop不当作执行或法义正确。

无损教师传输、两T并发、原生枚举预检查、CoRevOnly分发及跨版本接续均已有证据，按[执行报告](../reports/legal_skill_evolution_run_20261111/README.md)复用，不重复有效工作。原先所有失败、旧A/B/M1M2、LoRA及确定性资产保留；不重启历史路径或强行接入已淘汰方法。

完整研究和TRAIN补充均已发布并独立取回核验，收据分别为`fixed_study_publication_verified.json`及`TRAIN_precondition_publication_verified.json`。原队列全部结算；原阶段结论仍为“固定实验和实际分数收益成立，本研究未证实两项专门贡献”。

用户现已批准修改获取与更新安排并做有限原TRAIN验证。下一项实际工作：只读取原TRAIN、既有真实技能和来源暴露记录，核实能自然承载前提变化/依赖更新的候选对象，复用已有成功与反证；冻结小试来源、分工、强对照和工作量后实现并验证。共同底座按法律判断责任组织，公平开放给对照；不把读取整题答案、格式转换或创建新链重标为两项机制。有限TRAIN协议已冻结后自主执行必要模型验证；不重跑完整学习/矩阵或旧TEST，不进入论文，不重复申请本次范围许可。

恢复后已建立[原TRAIN与既有资产清单](../reports/legal_skill_evolution_run_20261111/protocol_revision_TRAIN_inventory.json)：128个原母来源身份保持，42个有原研究教师回执覆盖，其他86个仅表示未在这些回执中出现，不冒称新盲测；22个既有技能版本已登记，包括两臂独立§152获取资产及旧格式渲染依赖。渲染边不能作为法律责任共同修订，§152资产也只保留原已验证范围，后续共享或独立获取比较须明确成本。清单未读取评分标签或DEV/TEST样本，新增模型0。下一步核对SARA显式案情/法条依赖与ContractNLI原文条件变化，定义“给定事实、源规则参数、推导命题”的责任边界后锁定有限小试，不按TEST结果选来源。


## 历史：SARA有限TRAIN结果与当时的实现决定

[本轮真实结果与修复](../reports/legal_skill_evolution_run_20261111/ROLE_TRAIN_RESULT.md)：四臂六个原TRAIN母来源，两步获取/更新及两来源冻结复用全部完成；实际9项提议均create，参数/依赖端口0，Lift和CoRev仍未触发。Full学得一项家庭雇佣排除条件，但强对照也能学得，不能计作独立贡献。全部程序错用、字段误读、回退和版本表保留。

已按实际响应修复“仅引用法条也算案情证据”的检查缺陷，完整法律上下文和given法律中间事实保留；新增显式query_clauses作用域契约，新教师schema已真实生成、编译和执行。75项相关回归通过。后续真实检查仍将Bob是Alice父亲读成Alice是Bob父亲；从原问题逐字绑定双方姓名再次执行，错误仍在。格式/执行已接通，关系方向语义未解决，不重复同一失败请求。

本轮合计33E/9T，含有限试验30E/8T、具体修复2E/1T和显式主体绑定1E；累计9115E/150T、在途0，33E均OFF、reasoning空、正常stop。原206项正式/冻结绑定和原始账本不改；35项有限试验绑定及中间修复实际代码逐hash保全。没有资源缺口，不套用旧blocked、旧轮次或额度。

下一项实际工作：将相对角色直接分类改为有原文依据和方向的二元事实关系记录，由法律程序显式投影雇主/雇员；并修改共同获取步骤，先取得法源中有独立法律作用、实际被调用的规则对象，再做增量更新。先实现及离线反例回归，有明确变化后才作必要有限验证；强对照共享底座、独立获取。不能把公共关系抽取/格式修复认领为两方法贡献，不强拆字段、人工植入错误或原样批量请求；不重跑已完成小试、完整训练/矩阵或旧TEST。Goal保持active、未完成。


## 当前实际工作：源规则读取已修复，补齐CoRev编辑与关系实现

[合同有限验证](../reports/legal_skill_evolution_run_20261111/CONTRACT_TRAIN_RESULT.md)已完成。两臂真实规则获取、四臂两个更新及冻结复用全部保留；共享种子不冒称独立获取，Full的普通读取修订被Free与恢复的全端口对照吸收。原B3复用Full/Free/AllPorts .25、Generic .50、空库.25，各臂模式0。

[最新源规则验证](../reports/legal_skill_evolution_run_20261111/SOURCE_RULE_READ_RESULT.md)：公共法源读取排除原生假设、view ID和current_question，其他显式参数与完整源文保留；使用已有公开句界且只展示一套证据ID。4个固定合同已离线验证同源读取请求不随nda-5/7改变，91项回归通过。原Free联合提议重新执行完整4格：当前354全旧/仅生产者/仅消费者/联合=.50/.50/.50/.75，联合有2个真实程序原生答对；但历史8af与d50从1.00/.75降至.75/.50，拒绝且不学模式。8af包含证据ID范围失败，最后1E只验证该读取的明确修复，不重写整表。

原生局部联动并不等于语义通过：接收人/场景数组混入材料与活动，d50返回完整句子而程序要求类别原子。当前中间表示仍不可靠。原首个Lift案例另用真实字段做零调用反证，最小变化只有permitted_representative_classes，不再重跑该例追求耦合增益。新调用11E/0T，累计9218E/162T、在途0；模型OFF、采样和输出上限不变。原请求、失败、oracle及206项原绑定保留，原各阶段源码快照齐备。

CoRev进一步核对出两个明确实现差距：现有关系字段只有preliminary/terminal、类型和USE，无法区分实际消费者对False由Contradiction改为NotMentioned；原方案4.6的职责变化、使用方式和源关系未充分表达。当前模板仅存P，真实提议会改READ前提和绑定，连对自身旧程序的移植都失败。该缺口不替当前未通过的版本表免责，不把拒绝包加入模式库。[代码与实际程序反证](../reports/legal_skill_evolution_run_20261111/source_rule_CoRev_implementation_audit.json)。

下一项实际工作：实现有界、保持语义的完整READ/前提编辑模板及绑定校验，向Generic开放相同编辑能力；先用已有真实提议离线编译，不猜造新源常量，不绕过原生/历史准入。随后补充由实际程序、读写事件与源定位支持的职责差分，未核实的源关系保留unknown；不把粗声明当已验证语义。不追加教师请求、完整训练/矩阵或旧TEST；有明确实现和离线证据后才作必要定点验证。仍须真实可接受共同修订及另一母来源实际使用，不能以原生局部改善或工程补齐完成Goal。
