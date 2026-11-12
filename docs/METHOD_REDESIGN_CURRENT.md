# 当前证据与下一项实际工作

同一Goal **active、未完成**。目标、验收、授权及边界统一见[CURRENT_GOAL.md](CURRENT_GOAL.md)。唯一执行目录`/home/yndx/hhy/legal-skill-current`，开发分支`repair/lift-corev-activation-20261112`；main不改。

## 当前执行决定与最新实证

最后同步：2026-11-13北京时间。继续同一个Goal，保留五库、划分、模型和原生评分，校正方法设计。旧Lift/CoRev及A/B、M1/M2否定证据保留。系统Goal卡的初始文字不覆盖用户后续授权；执行以两份当前文档为准，不新建或重置Goal。当前两项贡献均未成立，先建立第一项。

**本次有限真实比较已完成，当前第一贡献尚无独立机制证据。** 两臂各独立获取/更新2T，初次资产逐字复用；两种Qwen读源各2E，全部stop却有复制、未绑定和源功能错误，旧读源剩余6份不派发。第二阶段用纯源程序替代失败接口，确定性执行原8份开发、固定2份TRAIN复用及同2份NoFactor，新增0E。

|实际比较|方法主路径native正确|自由程序主路径native正确|方法目标回退|
|---|---:|---:|---:|
|8母合同开发、每臂16目标判断|14/14|13/16|2|
|2母合同固定TRAIN复用、每臂4目标判断|0/2|0/4|2|
|同2复用NoFactor|0/2|不重跑对照|2|

每母合同4个原生视图，另2个非目标视图保持原fallback；开发方法18/32回退，复用6/8回退，回退不计核心成功。开发含fallback均分.84375对.75；复用.50对.375，差值包含历史fallback，不可用来证明新机制。方法G对premises的读取次数为0、bind_scope调用为0；19条规则和1个继承employees-owner模式未被实际使用。NoFactor两来源的源程序输出和全部视图完全一致，不能靠机械增加一个等价函数依赖制造消融。

原始方法响应seed9有Exception与ExceptionSet不匹配；依据其自己声明的唯一单元素集合构造子exception_set作确定性适配。原输出不改，适配路径、前后值、检查与单独执行manifest都保留。202项实现回归通过。实际源核对发现d936漏掉span38-39的保密条件；复用78ad漏被动式may be disclosed，e7b漏restrict disclosure许可而只留禁令。这些是学得程序覆盖/语义错误，不能用格式修复、类型通过或native标签补齐。未使用复用标签修改两臂。

证据：[完整阶段结果](../reports/legal_skill_evolution_run_20261111/scoped_acquisition_evidence/stage_result.json)、[源级核对](../reports/legal_skill_evolution_run_20261111/scoped_acquisition_evidence/source_semantic_review.json)、[每次请求与成本](../reports/legal_skill_evolution_run_20261111/scoped_acquisition_evidence/cost_and_request_ledger.json)、[可复现适配与执行脚本](../reports/legal_skill_evolution_run_20261111/scoped_acquisition_evidence/evaluate_adapted_outputs.py)。实际学习了新的外部源程序和owner敏感消费者；相对独立自由程序的开发差异存在，但跨来源复用与归纳算法作用尚未成立。

**继续检验源编译技能候选，已学程序作为可复用资产；局部例外窗口不单独算创新。** 原TRAIN中的信息描述角色、获授权接收者、所属主体、例外范围确有混淆，任务触发不是臆造；普通局部例外绑定吸收的是本次观察到的执行作用，不能由此声称独立创新或跨任务泛用性；也不能将它扩大成整个独立获取候选已经被否定。

[最新真实学习、程序和强对照](../reports/legal_skill_evolution_run_20261111/RELATIONAL_ACQUISITION_RESULT.md)：角色出现位置codec第一合同成对2E未解决动作/角色功能混淆，剩余3合同未派发。随后从同一8份TRAIN独立获取两份可运行源识别程序，另外2份原TRAIN复用，新增2T、执行阶段0模型调用。自由臂也自行选择同样的源编译架构。独立获取限于源识别组件，既有关系/推理程序共享，不冒充从零整套方法比较。两模型冻结，学习外部程序；不是手填字段、参数训练或沿用fallback充当主路径。

|同一10母合同、每臂40原生视图|主路径执行|主路径native正确|含历史fallback的整体均分|原历史非回归|
|---|---:|---:|---:|---|
|方法实际学得源程序|10|10|.825|通过|
|独立自由获取的源程序|10|9|.825|失败，d50退化|
|自由程序＋共享的简单例外绑定|10|10|.850|通过|

方法原三触发来源均值gain为+1/6，数值条件通过；当前10个实际使用判断已逐条对应原文依据，但不声称所有未使用字段或整个IR均被形式验证。30/40 fallback单列，不计核心成功。de427复用仍0主路径，5cad只有1；不能把局部结果当广泛泛用证据。

第三行是共享学得操作的执行控制，**不是新的独立获取**；两次教师费用全计。关闭方法的例外局部绑定后，10正确降至9并破坏历史；向自由程序提供同一普通操作即可恢复10/10。该结果支持操作有实际作用，也说明目前额外方法贡献尚未成立。方法原程序含两个公司缩写续行特判，去掉后10合同全部原始源记录和答案一致；原始程序保留，没有悄悄替换或宣称普遍等价。

此前三臂语义数组小试16主路径/13正确、自由9/5、删示例2/2的原结果仍保留，不被新结果覆盖。19响应与6语法变体零调用回放排除“解码语法强制填满角色词表”；27条旧主路径已补算实际证据重叠，span重叠不作为语义真值。

第二项尚未实现独立方法。“证据/反例触发修订”的泛称已有[RARR](https://aclanthology.org/2023.acl-long.910/)、[EviSkill](https://arxiv.org/html/2610.05030v1)、[De Jure](https://arxiv.org/html/2604.02276v1)、[VASO](https://arxiv.org/html/2606.05395v1)和[SkillEvoReg](https://arxiv.org/html/2609.30861v1)相关机制；从历史编辑学习上下文补丁也已有Refazer/Getafix。本次将第二候选具体化为“带源语义适用条件的修订学习”算法草案，尚缺实际重复修订机会及后续复用证据。使用已有算法并不自动否定法律问题中的贡献，也不能仅增加法律字段就认定差异成立。

## 下一项实际工作与恢复边界

纠正上一轮过早的整体降级决定：保留“学习可迁移的法律源编译技能”作为待验证候选，不继续扩充局部例外窗口来凑贡献，也不因为这一执行控制就换到另一个研究问题。共享操作干预只隔离执行；先前源程序比较共享了两份关系/推理产物，自由臂自行选择方法侧关系/P，所以它不是整套方法从零独立获取的检验。

已沿用并补读近邻论文和官方实现，具体机制、收益及差异见[文献与两张设计卡](../reports/legal_skill_evolution_run_20261111/LITERATURE_AND_METHOD_CANDIDATES.md)。CAA覆盖法规转代码，RuleChef覆盖获取/更新，LILO覆盖库归纳；EviSkill/SkillAdam及Refazer/Getafix覆盖相关修订。不能仅靠已有环节的组合名称宣称新贡献。

本次v5固定更新和比较已完成，不重跑acquire、evaluate或已暴露复用题。下一项集中校正**G的获取/更新算法**：当前教师自由生成G绕过了归纳器，必须使已保存源反例实际改变可复用的编译规则。先用现有8份开发原文/真实派生做离线算法反证，对照完整自由程序、正确规则缓存及最接近已发表机制；不重复已证等价的字面NQG，不把同义AST改写成显式调用当新能力。若仍只得到普通修补或缓存等价，明确降级而非继续同正则路线采样追正例。此项算法工作在原授权内继续，不是等待许可；没有新的模型队列或完整训练。

后续决定性检验仍是**端到端独立获取**：相同原文、监督、初始公共底座、语义反馈及可比资源，双方独立取得完整方法，不提供方法新学出的关系/P/G；自由对照可选相同分解、文法、新节点和完整程序。完整获取与修补费用计账，评分、源依据、历史和fallback口径保持。已有8+2合同是开发材料，不冒充未见验证；需要实际复用时从原TRAIN中事先固定未参与该机制修补的来源。只执行本项有限已定义工作，不重复旧队列或完整研究。如果真正独立强对照吸收效果，再按该层证据作决定。

恢复先读本文件与CURRENT_GOAL.md，再核实唯一账本和实际进程。`artifacts/legal_skill_evolution_source_program_acquisition_20261113/completed.json`及`postrun_audit/mechanism_interventions.json`均已结算；此前角色codec和原三臂也已关闭，**不要再次acquire/evaluate或派发其剩余合同**。原始代码、提议、响应、拒收、账本和较早不同源码字节均保留。普通研究决定在现有授权内自主继续，不逐轮问许可。

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

累计**9330E/181T**、在途0：执行9311完成/19失败，教师176完成/5失败。本轮新增4E/4T，9511条请求；原9503条逐行保持。执行模型45665输入/12675输出token、请求耗时合计387.02秒；4T合计944.57秒，教师CLI不提供实付账单，不把缺失账单写成零费用。唯一账本`artifacts/rr_v2_preflight/research_ledger.sqlite3`保持，原冻结条目及失败全部保留。

v2教师资产、v3/v4失败读源、v5更新及确定性结果均已结算；旧源程序8+2、角色codec和本次v5都不是待跑队列。无研究客户端在运行，模型服务保留。thinking OFF、原采样、8192上限和授权教师不变，无新机械上限。当前Goal active、未完成，没有新的完整训练、DEV/TEST或论文。

项目归并先独立复制42,520文件，未提交/暂存/未跟踪修改和同一账本均保留；旧树在history，模型服务未重启，目录整理0模型调用。[目录与归档规则](PROJECT_LAYOUT.md)、[校验收据](workspace_unification_20261112.json)。后续重大替换仍先独立归档，再修改当前目录。
