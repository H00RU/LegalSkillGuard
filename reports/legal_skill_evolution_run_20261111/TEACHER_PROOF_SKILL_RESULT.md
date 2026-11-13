# 教师证明技能：真实更新、冻结复用与阶段判断

2026-11-13。同一Goal active、未完成；本次没有完整训练、DEV/TEST或论文。**教师确实完成了外部程序学习与反馈修订，但本版没有贡献增益：三臂在两条获取TRAIN上从1/2变为2/2，冻结的后四条TRAIN均0/4主路径覆盖。** 这些是6个原TRAIN母案例，共用同一份§63及关联法源，不能当6部独立法律或新盲测试。

## 1. 验收与实际机制

用户已明确：完整ours必须在主要任务指标上明显超过基线与相关强方法；分别删除两个贡献，均需出现可解释的任务指标下降。教师学习、成熟算法和模块组合都可以成为方法实现方式，不要求另造host归纳器；生成程序、同例修复、节省成本或流程跑通不能单独满足最终验收。当前三臂为早期筛选，不足以替代完整ours/−贡献一/−贡献二的最终独立消融。

本轮第一候选是教师蒸馏可复用法律证明技能；第二候选是根据支持／反驳证明缺口定向修订。公共底座沿用现有纯Python执行器、字段读取、源引用和原生评分。source-only初始获取仅提供原法源及前两种公开问法，不给案例事实或标签；教师实际返回源码、源引文和读取接口。后续监督修订只用前两条原TRAIN事实、标签和实际执行诊断，不再声称修订仍是source-only。

|臂|初始外部技能|独立教师修订|
|---|---|---|
|Full|TeacherProof实际程序|支持／反驳证明缺口修订|
|ProofFree|同一TeacherProof初始程序|完整信息下的自由反思|
|CacheFree|另一次独立获取的自由Python政策缓存|完整信息下的自由反思|

Full−ProofFree筛查修订作用；ProofFree−CacheFree筛查普通修订下的获取差异。后者不是完整ours删除第一贡献的最终消融，不能据此宣称两项归因完成。独立控制允许完整法源、相同架构、helper、缓存和任意自由修补。

为区分实验数据与被检验算法，控制首次派发前移除了候选修订配方本身，原文、案例、监督、轨迹及共同GIVEN澄清完全不变；Full在途请求与结果保持。更改无新增案例、标签、种子或物理重试。[修订协议](teacher_proof_skill_evidence/revision/protocol.json)、[派发边界说明](teacher_proof_skill_evidence/revision/control_comparison_boundary_note.json)、[实际控制输入修订](teacher_proof_skill_evidence/revision/control_comparison_amendment.json)。

## 2. 实际学到了什么

首题原文给出已婚、夫妻分报及配偶可使用itemized deduction，程序实际执行§63(c)(6)(A)对应条件；两臂均主路径答对。方法初始路由漏掉applies词形，已用可复核的公共适配修复；除_kind外函数AST不变，原教师输出和修复前行为保留。ProofFree修订又出现相同路由缺陷，也接受同一个公共修复，不能把它计算为定向修订的独立优势。

第二题案情明确给定：Alice和配偶分别有600美元additional standard deduction，目标依据§63(c)(3)合计1200。两份初始程序却索取未提供的年龄、失明、配偶收入等前提，真实读取保持unknown，因而两臂均回退待处理。所有三个教师修订都学到读取明确GIVEN的金额，不再重建其全部前提；实际程序随后求和并比对主张，均答对。

Full实际执行_c3_values→_given_c3_values；ProofFree执行_additional_values→_given_component_total；CacheFree执行_additional_totals→_given_additional_totals。代码、输入及返回完整保留，非host补写法则或答案。它证明教师能完成反馈→程序更新→实际执行，但普通反思也学会了，尚无额外指标作用。[原始教师与源码](teacher_proof_skill_evidence/revision/)、[初始真实执行](teacher_proof_skill_evidence/initial_execution/)、[修订后逐条执行](teacher_proof_skill_evidence/revised_execution/calibration/)。

有一项实际正确性问题不能隐去：Full和ProofFree的reader都把问题中的1200作为“案情明确给定总额”返回，证据仅来自hypothesis。预先固定的共同绑定检查拒绝了这两个值；未把它们修成其他数字，也不称原始reader输出完全语义正确。程序实际消费的是案情支持的600和600，并真实完成求和。其余未知事实未转False/0/空列表。CacheFree没有这个被拒字段。[共同读取与绑定检查](../../experiments/legal_skill_evolution_teacher_proof_evaluate.py)、[对应语义审查](teacher_proof_skill_evidence/revised_execution/calibration_review.json)。该审查仅覆盖对应实际判断，不宣称全法源形式等价或全分支证明。

## 3. 冻结结果与具体原因

|系统|修订后两条TRAIN：主路径正确／全部|后四条固定TRAIN：主路径正确／全部|后四条需回退|
|---|---:|---:|---:|
|Full|2/2|0/4|4/4|
|ProofFree|2/2|0/4|4/4|
|CacheFree|2/2|0/4|4/4|

后四条分别问§63(f)(2)(A)、§63(d)、§63(c)(7)(ii)、§63(c)(5)。三份程序的plan均unsupported，实际evaluate返回unknown，没有调用源规则函数。故这不是四题模型计算错误、输出截断、类型失败或故意提高门槛；是学得程序仍只有两个问法入口。回退没有执行，不把它写成4次最终答错，也不计核心成功。

f2的源语义曾作为c3计算子过程被取得，但未成为可供新目标调用的独立子结论；另外三类目标没有对应取得的程序。**当前产物是窄目标答题程序，而非已经证实可供不同子目标使用的证明技能库。** 本轮新增两个正例不能外推整体就绪。取得4条结果后不修改程序、不按其标签修补、不追加同例变体。

[冻结收据](teacher_proof_skill_evidence/revised_execution/freeze.json)、[全部12条冻结执行](teacher_proof_skill_evidence/revised_execution/frozen/)、[完整统计](teacher_proof_skill_evidence/stage_result.json)。后四条unsupported没有触发模型请求，新增调用0；无冻结后教师调用。

## 4. 实际费用与保全

新增**10E/5T**，全部物理请求完成，无失败／底层重试遗漏；累计**9486E/200T、9686行、在途0**，此前9671行逐条保持。教师110764输入／52587输出token（含27435 reasoning，另有13440 cached input包含在输入统计中），服务时间1025.504秒；执行22302输入／3571输出token，服务时间100.700秒，10次均正常stop、thinking OFF，最大单次输出776token。模型与采样配置不变。

Full与ProofFree共享的TeacherProof初始化，在每臂逻辑成本中均计入，物理总账只计一次。每臂逻辑上均为一次初始化、一次修订、两次初始读取及两次修订后读取；冻结回退检查新增0调用。教师逻辑服务时间Full约491.235秒、ProofFree约457.776秒、CacheFree约340.468秒；当前没有同等正确性下的教师成本优势。服务秒不等于用户墙钟等待时间。

执行增量API现金0，GPU实付分摊未知；教师沿用授权CLI，无可访问发票，现金费用记未知，不称全流程免费。[逐请求token／耗时、hash与旧账保全](teacher_proof_skill_evidence/cost_and_preservation.json)。原始响应、前后程序、失败及无调用的调度问题全部保留；不重置账本，不直接改main。

## 5. 近邻与下一项实际工作

[PercepLog-0](https://aclanthology.org/2026.findings-emnlp.2099.pdf)已有按目标抽取事实与反向链；[官方仓库](https://github.com/HLR/PercepLog)目前仅README，不能声称复现其官方代码。[ReaComp](https://arxiv.org/html/2605.05485v1)已有从轨迹取得可复用求解器；[法律proof-carrying方法](https://www.mdpi.com/2504-2289/10/9/295)已有源链接规则与确定性执行。因此候选应由真实机制差异和强比较支撑，不能凭“教师＋程序＋缓存”命名成立，也不能因它们是成熟组件而拒绝验证。

**关闭本版有限小试，不扩大完整训练或评估矩阵；Goal仍active、未完成。** 下一工程工作是在保留有效Python程序与GIVEN更新的基础上，使已学法律子结论具有源作用域、输入和输出的可调用合同，由通用查询过程实际复用；确定性host只做调用与检查，不补未取得的法律规则。未取得规则仍unknown。这是修复当前机制未兑现的必要实现工作，本身不自动算创新。后续真实比较须包含独立完整原文程序／持久规则缓存等强控制；若普通缓存已吸收效果，如实处理。两个贡献仍须满足主任务增益、独立消融及完整ours优于强方法的最终条件。

## 6. 接续接口拆分与离线核对

本节与上面已冻结的小试分开计账。教师接收原已学Full程序、同一法源和新的属性调用接口，没有接收后四条检查案例、问题、标签或结果。它实际返回10个有原文引文、输入字段及函数的单元，全部标记复用既有逻辑；没有新增法源或补造未取得的规则。法律程序只接收单元标识和案情支持的事实，金额主张与原生标签留在调用层。

离线核对实际执行10个入口，空输入全部保持unknown，声明的函数均被调用。仅重放原两条获取案例已有的真实reader绑定，原答案保持；8项公共接口回归通过。上述结果证明接口能执行并保留这两个已有行为，没有增加独立来源、真实executor调用、主指标收益或贡献证据。

审查还发现尚未解决的具体不兼容：6个单元只有quantity头，其中部分法律条款既规定适用条件，也规定金额；金额计算入口不能直接回答适用性。源程序内部已有部分条件计算，但当前没有提供相应独立predicate输出。不得通用地用“金额大于零”转成适用，也不得把缺少相应入口视为新目标已验证。下一工程改动应明确区分条件与效果，保留源依据及unknown；是否需要为某一条款提供两种属性取决于真实任务，不追加全条款覆盖要求。这个接口改动本身不占任何贡献。

本次新增**0E/1T**，累计**9486E/201T、9687行、在途0**，原9686行逐条保持。教师25134输入／17398输出token，含8364 reasoning，服务333.454秒；CLI现金发票不可用，费用仍记未知。绑定的6份源码与测试在该请求期间哈希不变。原四条冻结检查没有重跑，仍保留原失败结果；没有完整训练、DEV/TEST或新评分。

[教师原始响应](teacher_proof_skill_evidence/callable_rule_refactor/teacher.json)、[实际输入](teacher_proof_skill_evidence/callable_rule_refactor/input.json)、[协议与绑定](teacher_proof_skill_evidence/callable_rule_refactor/protocol.json)、[可执行单元库](teacher_proof_skill_evidence/callable_rule_refactor/library.json)、[逐入口审查、两条重放及账本保全](teacher_proof_skill_evidence/callable_rule_refactor/semantic_interface_audit.json)。**两项贡献仍未成立，Goal保持active、未完成。**

## 7. 新TRAIN法源独立获取、真实比较与事实绑定修复

接续完成了条件／效果分离：教师增加5个适用条件函数，原法律函数AST逐项保持；调用层直接执行声明函数，保留未知。原两个获取案例重放不变。本节使用原TRAIN中未参与本轮机制修补的§151三个母案例，同一法源及关联§152／§68，不当作三部独立法律或新盲测。两教师独立读取相同完整法源和通用任务说明，没有接收案例正文、原生问题、标签或另一臂的程序；程序在首个真实reader前冻结。方法取得16单元，自由缓存取得26单元，允许相同架构和完整源处理。[固定协议](teacher_proof_skill_evidence/callable_source_trial/protocol.json)、[两份真实获取](teacher_proof_skill_evidence/callable_source_trial/)、[冻结收据](teacher_proof_skill_evidence/callable_source_trial/freeze.json)。

方法返回的条款标识包含§符号和标题，严格检查首次拒收。提取其唯一显式条款编号后无歧义恢复，法律程序字节保持；原失败、输入和源码快照保留。该确定性公共适配在任何native执行／评分前记录，并一致适用于两臂，没有重新调用教师。[源码调整收据](teacher_proof_skill_evidence/callable_source_trial/clause_normalization_source_amendment.json)、[原失败与恢复](teacher_proof_skill_evidence/callable_source_trial/ProofSkills/recovered_offline_check.json)。

|固定3例的原始真实结果|主路径给出答案|原生答对|需回退|
|---|---:|---:|---:|
|ProofSkills|1/3|1/3|2/3|
|IndependentCache|1/3|0/3|2/3|

**该表不能认定为有效方法增益。** 方法唯一答对项把问题中的“Bob the dependent”作为GIVEN事实支持，原检查只识别explicit／state措辞，漏掉expressly give。真实原始reader没有提供案情证据；不得补换引用。对两臂一致施加“事实前提必须有facts支持”的必要检查后，原6条记录离线重放，方法三条均unknown，表面差距消失。原始结果不覆盖。[原始统计与费用](teacher_proof_skill_evidence/callable_source_trial/stage_result.json)、[事实支持重放](teacher_proof_skill_evidence/callable_source_trial/facts_only_replay/summary.json)。

另两条的原因已定位：§151(d)(3)(B)方法读到了276932、250000及未婚，但程序额外连接§68暂停条件，要求未读取的tax-year-begin字段；自由缓存不接收明确GIVEN的250000，而从未知filing_status重建阈值。§151(d)(2)双方询问deduction allowable，而案情明确给定exemption entitlement，均未消费源§151(a)的连接。它们是所学程序／事实接口和查询作用域的具体缺口；材料并非不支持推理，不是截断或类型失败。不得由host填默认年份或补法律连接。

随后只针对已暴露的事实证据缺陷做2次工程确认：相同案例、原程序及字段不变，只给facts分配证据ID，原生问题通过invocation_arguments保留为查询上下文；没有教师或标签输入。方法的GIVEN dependent现在实际引用facts，源§151(c)函数返回True；其另一个spouse字段仍误取Alice／Charlie，但未被提前返回的GIVEN路径消费。对照也误取该spouse关系并返回False。**这是修复后的真实同例执行，不是新增独立验证或创新增益。** [实际工程恢复](teacher_proof_skill_evidence/case_evidence_recovery/)、[逐问题语义与机制审查](teacher_proof_skill_evidence/callable_source_trial/semantic_and_mechanism_review.json)。

本节接续共**8E/3T**，累计**9494E/204T、9698行、在途0**，此前9687行逐条保持。教师60209输入／38236输出token（含14460 reasoning）、739.108服务秒；执行11471输入／1382输出token、38.950服务秒。8个实际wire均thinking OFF、max_tokens8192，全部正常stop。教师实付发票及GPU分摊未知，执行增量API现金0。[逐请求成本与保全](teacher_proof_skill_evidence/callable_source_trial/total_cost_with_engineering_recovery.json)、[实际wire配置核验](teacher_proof_skill_evidence/callable_source_trial/executor_wire_profile_check.json)。16项相关离线回归通过。原三题比较结束，不继续同例提示变体；无新来源、DEV/TEST或完整训练。

## 8. 与最近邻的差异判断及下一步

当前两个名称仍是待验证候选，不是两个已成立贡献。最近邻已经包含重要底座：PercepLog-0的Algorithm1使用LLM辅助目标抽取／代换并展开规则；ReaComp §2.2从轨迹取得可复用求解器；法律proof-carrying方案已有源链接规则、defeater、证明和验证触发修补。因此“教师生成程序”“按需读取”“保留证明／缓存”“报错后修补”单独都不能承担本项目的差异主张。[PercepLog-0原文](https://aclanthology.org/2026.findings-emnlp.2099.pdf)、[ReaComp原文](https://arxiv.org/html/2605.05485v1)、[法律proof-carrying原文](https://www.mdpi.com/2504-2289/10/9/295)。

我们的拟研究增量仍是法律规则获取与复用中的可靠性，以及反馈驱动修订在后续案例中的独立作用。本轮没有证明它们；代码接口差异和个别正确路径不代替机制差异。下一项先将**查询人物／期间与案情前提分开，并让实际源程序正确消费明确GIVEN的法律中间命题**；这属于修复已定位的实现／学习对象缺口。随后必须明确教师究竟学到了什么、如何更新及何处超出普通持久缓存／同信息反思，再预先固定原TRAIN中的后续比较。没有具体机制差异时不扩完整建库或批量实验。完成判定仍要求完整ours优于强方法，且两项各自消融有可解释任务指标下降；不新增零回退、全分支实测或固定涨分门槛。**同一Goal active、未完成，不重启或重置。**
