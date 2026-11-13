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
