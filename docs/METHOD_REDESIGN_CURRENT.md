# 当前证据与下一项实际工作

同一Goal **active、未完成**。目标、验收、授权及边界统一见[CURRENT_GOAL.md](CURRENT_GOAL.md)。唯一执行目录`/home/yndx/hhy/legal-skill-current`，开发分支`repair/lift-corev-activation-20261112`；main不改。

## 当前执行决定与最新实证

最后同步：2026-11-13（北京时间）。保留五库、划分、模型和原生评分，校正方法设计。旧Lift/CoRev及A/B、M1/M2的否定证据保留，不再锁定为最终两贡献。先建立一项完整贡献，再建立独立第二项；当前两项均未成立。系统Goal卡仍显示初始文字，恢复不能据此推翻用户后续授权；最新任务状态由本文件和CURRENT_GOAL.md共同给出。

**第一候选：与实例事实分开的参与者归属及动作/限定作用域关系编译技能。** 已有真实可运行实现，教师从相同8份原TRAIN合同独立获取关系含义、字段/归属约定和程序；运行时读取当前合同，不带旧实例值。固定另外2份原TRAIN合同检查复用，不是新盲测。当前实现只接通ContractNLI的nda-5/7，不把表示潜在通用性说成五库泛用性。原TRAIN确有员工所属主体、访问与披露动作、嵌套限定错绑，因此任务触发真实；能否形成可复用增量仍由结果决定。

[固定三臂验证已结算](../reports/legal_skill_evolution_run_20261111/RELATIONAL_ACQUISITION_RESULT.md)：两臂独立获取，另有“仅删除示例、保留旧程序”执行控制。新增30E/3T；第3次教师只修复实际未声明字段及所属主体错误，已合格的自由获取提议原样复用，未重复调用。

|固定10母合同、每臂40原生视图|真实主路径数|主路径native正确|fallback比例|含既有fallback的平均grade|
|---|---:|---:|---:|---:|
|作用域关系获取|16|13|60%|.725|
|同信息自由获取|9|5|77.5%|.675|
|仅删示例、保留旧程序|2|2|95%|.775|

主路径只适用每母合同的2个目标视图，其余2视图按原范围fallback，全部保留整体分母。上述标签正确数不是全部IR语义正确数。关系候选在原三触发来源平均gain为+1/12，但354/62f历史退化，未通过原历史非回归要求，**未准入**。自由臂同样未通过；删示例控制无触发gain。不能用16条可执行路径或fallback较高的总分代替第一贡献成立。

已定位的真实语义缺口：候选常把整个允许角色词表当作当前条款事实；4d4e的正确第三方标签引用内部跨部门限制，5cad的正确第三方标签引用保密义务排除条款。de427及5cad的员工许可确有原文支持，但记录还添加未被支持的角色，不能把两复用合同3个native正确路径称为3份完整合格IR。语义检查尚未全部完成，原输出保持不改。自由臂有1条8192截断，其余低覆盖主要为真实程序不处理，不推定为新的系统接口故障。

**第二候选尚未形成独立方法。** “答案对但证据错时修订技能”是需解决的现象，但宽泛机制已被[RARR](https://aclanthology.org/2023.acl-long.910/)、[EviSkill](https://arxiv.org/html/2610.05030v1)及[De Jure](https://arxiv.org/html/2604.02276v1)相关的归因修复、证据回放及选择性规则修复覆盖，不能按此表述宣称没人做过。目前没有足够具体的独立更新算法、实现及增益证据；需明确学到了什么可复用对象，并与同信息的普通证据监督/整体修订对照区分。用户的质疑已纳入，不是新增暂停指令，也不是要求每个底层算法全新。

## 下一项实际工作与恢复边界

1. 先用本次已保存的真实请求、schema、完整响应和实际使用记录，离线核查“角色词表整体复制”及动作/作用域错误。区分模型误读、提示/接口负担和约束解码行为；不得未经复现就声称数组解码器有缺陷，也不得用答案填字段。
2. 完成源依据/实际证明的对应检查。当前评分调用没有传证明span，缓存中的evidence_f1=0不代表已测证据质量；必要时离线另算并单列，不能用span重叠代替角色与动作语义正确性。这是已有语义验收的补齐，不新增精确证据零误差门槛。
3. 根据上述具体缺口确定第一候选的必要最小修改及离线回归；如果普通同信息获取吸收收益或仍无机制作用，如实处理，不把本轮继续扩成完整训练。第二项只在具体学习对象、独立更新算法及最近邻差异成立后进入有限验证，不继续用泛称凑第二创新。

恢复入口：`artifacts/legal_skill_evolution_relational_acquisition_v2_20261113/completed.json`、同目录protocol.json和targeted_source_semantic_review.json。此队列已全部结束，**不要重新执行acquire/evaluate或重启旧客户端**。当前无实验请求在途；无需等待用户逐轮许可，后续有实质修改和离线依据才做必要有限真实验证。模型服务保持运行不重启。没有新完整训练、DEV/TEST矩阵或论文队列。

## 可复用资产与已完成反证

- [源编译](../reports/legal_skill_evolution_run_20261111/SPAN_COMPILER_RESULT.md)：真实共享获取资产及12/12原合同主路径正确；方法教师超时，不能冒充独立获取；新合同0覆盖、实际合并0。
- [NQG组合归纳](../reports/legal_skill_evolution_run_20261111/COMPOSITIONAL_COMPILER_RESULT.md)：官方代码、61配对、17组合规则和61/61回放；9合同与普通模板结果相同，两诊断合同仍0覆盖。已有等价反证不重跑。
- [局部神经绑定](../reports/legal_skill_evolution_run_20261111/NEURAL_BINDING_RESULT.md)：7E/0T、真实转义引号解码修复、主体/嵌套错绑原始证据；旧队列第4合同未派发，但不再作为待跑队列，已由本次新协议覆盖相应TRAIN来源。
- [TRAIN适配与模块证据](../reports/legal_skill_evolution_run_20261111/METHOD_EVIDENCE_AND_TRAIN_FIT.md)：128母来源/280视图血缘及隔离逐项核验；MAUD题级材料、SARA引用和Airline单政策边界保持。材料有效不等于新机制已匹配或获得证明。

## 较早诊断与真实更新证据（已完成，不重启）

本次源接口候选真实读取9份、独立对照真实执行9份，全部正常stop、thinking OFF，126项回归及原206项冻结哈希保持。候选在三个触发合同上相对原NoSkill均值+1/12，对照-1/12；历史非回归均失败。正确目标标签不代表返回的整个源字段正确，源级语义审查材料与原始响应已公开。

对照首次9请求HTTP400是工程缺陷，根因是现有vLLM拒绝显式数组uniqueItems，而不是空值标签或模型推理失败。客户端未及时停止，九次均计入；已修复传输与系统性WireError停止处理。原始提示和严格host校验保留，只从解码器schema移除其本来忽略的关键字；18个原请求的前后解码文法逐一一致、修复schema通过实际服务的离线检查、重复证据ID仍由host拒绝。之后只重试9个失败对照请求，未重调教师或候选读取。修复前原结果、52个源码快照、全部失败与两版协议保持。

[片段接入程序的真实结果](../reports/legal_skill_evolution_run_20261111/FRAGMENT_PROGRAM_RESULT.md)：Full/Generic从同一真实Free B2库独立生成更新，两臂354 .50→.75、历史8af 1.00与d50 .75保持，固定62f从同旧库.25→.75；四母来源nda-5/7各8视图/臂均真实程序答对，其余视图按原范围fallback。新增4E/2T。收益来自普通文本程序获取与修订，被Generic吸收，不是两项独立机制证明。

Full原管线漏看新伴随输出general_third_party_prohibition，误存1个接口变化模式。已按实际失败修复所有依赖端口跨版本兼容性检查，离线重算Full合格模式为0；原程序、准入、原始库和结果保留，修正库另存。Generic保留1个通用编辑记忆，后续实际模式引导修订0。118项相关回归通过；16条实际程序路径零调用精确重放一致，原50个被测源码文件有快照。元数据键序导致的两次重复读取完整计账，纯片段wire已规范，普通语义wire保持。

[最新固定程序强简单对照与受限证据](../reports/legal_skill_evolution_run_20261111/MECHANISM_VIABILITY_REVIEW.md)：完整原文片段零模型调用复现原四来源结果。评分前按原TRAIN顺序固定的后三个CNLI母合同d936/e671/442上，Full 0/6、Generic 1/6目标判断正确；其余视图沿用真实历史fallback并保留母来源分母。这是共享资产的离线执行控制，不是独立获取或新盲测。

实际Full AST逐片段检查表明三合同没有任何现有许可/禁止门命中；任意逐字片段子集、重排或重复都不能修复六项错误，必须改变P或学习对象。消费者现有布尔接口可表达目标，只是反事实可达性，不是已取得的源依据修复，也不强迫共同修订。没有写回人工值、补规则或用标签改程序。该结论排除当前固定程序的selection-only路径，不证明两机制普遍不可能。

当前库所有法源端口已经READ，无常量Lift可作用块。原TRAIN中Airline24来源共享同一显式规则文本，SARA24来源有8个显式文本；CNLI/MAUD各24不同文本。案例变化不等于法源变化，文本不同也不保证固定P可由参数重绑定迁移。现有程序只覆盖少量词面，不能把它的局部正确概括为稳定法律能力。

## 原完整研究与历史失败保留

原128母来源/8批、42个DEV点、B8七系统五库各32 TEST及迁移已经结算，不重启。formal77和freeze129项绑定保持；原实验完成不是Goal成功凭据。

原Full B8 DEV五库等权.5932961，空库.4813387；TEST Full .5384792、AllPorts .4261885，差+.1122908，校正98.75%区间[.0632968,.1631957]。原始提议103 create、6 revise、0 Lift；接纳21 create、3 revise，B8依赖端口和CoRev模式0。Full76/352原生视图走程序、16个全对、276回退，跨库最终路径0。原收益成立，但来自普通获取/过程修补，不支持两专门机制。

- [原阶段复核](../reports/legal_skill_evolution_run_20261111/FIXED_STUDY_STAGE_REVIEW.md)、[主要执行者判断](../reports/legal_skill_evolution_run_20261111/primary_scientific_review.json)
- [原逐来源结果](../reports/legal_skill_evolution_run_20261111/fixed_TEST_source_results.csv)、[TRAIN轨迹](../reports/legal_skill_evolution_run_20261111/formal_TRAIN_trajectory.json)、[DEV汇总](../reports/legal_skill_evolution_run_20261111/formal_DEV_summary.json)
- [原获取对象缺口](../reports/legal_skill_evolution_run_20261111/TRAIN_PRECONDITION_DECISION.md)：48个批初库均无旧依赖链；四个依赖包全部create且未过原准入，不能重标为CoRev。
- [SARA有限验证](../reports/legal_skill_evolution_run_20261111/ROLE_TRAIN_RESULT.md)：33E/9T，创建与关系方向问题，未支持两机制。
- [合同有限验证](../reports/legal_skill_evolution_run_20261111/CONTRACT_TRAIN_RESULT.md)：旧获取、两步更新与复用保留，普通Lift修订被强对照吸收。
- [源读取、完整编辑、职责匹配及失败修复](../reports/legal_skill_evolution_run_20261111/SOURCE_RULE_READ_RESULT.md)：包括复杂记录截断、原子语义unknown、引用/守卫修复和全部费用。原单字段已足够的反证不重跑。

旧A/B、M1/M2、LoRA及确定性受限资产均为历史参考，不恢复已淘汰路线。原资料全文保留在Git历史、reports、artifacts和独立归档。本次两份长执行文档整理前的独立副本位于`/media/sangfor/vdb/legal-skill-backups/design_execution_decision_20261112/`；提交ade374c保留其原文。

## 当前运行、资源与恢复

累计**9324E/175T**、在途0；执行9305完成/19失败，教师170完成/5失败，全部失败保留。最新关系获取小试新增30E/3T，三臂各10原TRAIN合同已经结束，无运行中的实验客户端；旧session90981和43716均不能当作活任务。模型服务保留。155项相关回归此前通过；本次同步核验原206项冻结条目、9466条旧账本及当前协议绑定源码，原始结果不覆盖。

唯一账本`artifacts/rr_v2_preflight/research_ledger.sqlite3`，最新协议/结果`artifacts/legal_skill_evolution_relational_acquisition_v2_20261113/`，本次修复前提议`artifacts/legal_skill_evolution_relational_acquisition_20261113/`。运行已结算，不重调已完成请求。此次文档和账本核对新增0模型调用。thinking OFF、原采样、8192上限及已授权教师保持；没有新资源请求、旧调用上限或修复轮次限制。用户Resume和协议调整持续有效。Goal active、未完成，下一工作如上，不因压缩或本轮答疑暂停。

项目归并先独立复制42,520文件，未提交/暂存/未跟踪修改和同一账本均保留；旧树在history，模型服务未重启，目录整理0模型调用。[目录与归档规则](PROJECT_LAYOUT.md)、[校验收据](workspace_unification_20261112.json)。后续重大替换仍先独立归档，再修改当前目录。
