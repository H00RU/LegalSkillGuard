# 当前证据与下一项实际工作

2026-11-14。同一Goal **active、未完成**。目标、验收、授权及边界只由[CURRENT_GOAL.md](CURRENT_GOAL.md)规定。唯一项目`/home/yndx/hhy/legal-skill-current`，开发分支`repair/lift-corev-activation-20261112`，不改main。历史暂停、Goal卡和PID不触发操作。

## 当前状态与决定

继续C（诊断驱动开放法律规则学习）与U（法源—程序联合更新程序），不换候选、不新建Goal。最近两段固定真实研究均已结束：joint_acquisition_evidence_set与diagnosed_update_scalar，各有TERMINAL_PRESERVATION.json，模型在途0。session91050、23423均正常结束，不能重复启动。当前进行确定性来源φ的离线接口补齐，尚无新的模型任务。

当前研究入口`experiments/legal_skill_evolution_diagnosed_update_train.py`保留最后scalar run；其冻结版本在该run/source_snapshot。随后源码为离线source_program接入作了修改，故不能按新源码重跑已完成scalar协议。下一次真实工作须保存新的明确continuation绑定，复用付费提议/读数与所有旧账本，不恢复旧队列或机械上限。

## 已完成的真实诊断更新

|范围|C共同拟合|同提议/读取NoFit|独立自由更新|
|---|---:|---:|---:|
|八母获取，原生正确/32|23|19|24|
|获取核心程序执行/32|28|28|26|
|冻结后c46f/96361，原生正确/8|5|4|1|
|冻结后核心程序执行/8|6|6|4|

未调用fallback，未覆盖保留原分母。真实G拟合改变预测，原生层面有4个获取及1个后续正确增量；**对应法源语义核查尚不支持将该差值计为独立贡献。U真实φ/G字典仍为空，两项均未成立。** [当前报告](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/update_train_result.md)、[逐来源与实际反馈](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_diagnosed_update/source_results.json)。

c46f的唯一NoFit→拟合额外正确依赖把返还/销毁指令读取为明示留存禁令，超出该操作定义。96361有直接支持的员工许可、协议终止触发，但选中G把advisors变成consultants并漏了明确必要用途限制。原生分数不改，不把部分片段支持写成整体语义正确。[逐路径证据](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_diagnosed_update/postfreeze_source_path_review.json)。后续两母只作冻结后一次检查，不用于反复修补和补评分；同类误读已有原八母TRAIN证据。

此轮两臂正文完全相同，均见原八母原文、合法监督、双方实际历史、共享C库及诊断，hash为01c67ce7ce33303bd38606c6db5e96d3678c667923314306ad9494efae1c3ef5。原先12个错误中至少11个不能靠现17条选择消除，故实际路由到开放读取/语言/消费者修订；这仅是当前候选下界，不是原文歧义或缺概念证明。严格表示冲突证书仍0。

C实际提出17操作/19候选；Free选择确定性原文程序、神经操作0。C278889输入/27352输出token（含9866reasoning）、509.943服务秒；Free278384输入/11305输出token（含5765reasoning）、215.584服务秒。Free第一次在预留前因串行策略被拒、物理调用0；C结束后串行派发Free一次，C未重取。两份原始提议、失败和成本保持。

## 已解决与真正剩余的实现问题

1. 源读取使用choice与当前单元ID，host取回完整原文，分类与语义仍由实际读取负责。全源absence只在实际全源及明确操作声明下成立，unknown/未读不当否定。token预检保留8192输出预留，重复同一证据ID仅作幂等集合恢复，原raw失败保持。
2. 第二母真实类型失败已修复：关系recipient_role与choice是有限字符串域，旧术语层只认text。仅从已学词汇声明8角色/25choice值，域外、错域、数字、结构类型冒充、原生答案仍拒绝。两份教师及20次执行响应不重取，完整恢复第二母17条回答、物理请求0；第一母输出/评分完全相同，直接复用。403项相关回归通过。
3. **当前主缺口是φ的确定性/组合读取实现。** 设计允许该类计算，旧C新增概念却只能作为神经问答执行，Free能任意执行原文程序。重复改问句没有解决许可/禁止极性和条件遗漏。现已把已学source_program接到observe的规划之前，同一类型/出处检查后进入实际关系观察；编译器可从真实source_functions更新它，U支持该组件并使旧fit失效。

上述接入复用了本轮已付费Free程序及其真实完整函数，不写host法律分类器。在8份原TRAIN上实际执行，得到与原Free源输出逐字段相同的结果，模型新增0；[实际程序/观察等价](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_diagnosed_update/actual_program_equivalence.json)。这是公共能力补齐，不是新的独立获取或方法收益。新增3项回归后完整相关unittest **406项通过**。

## 唯一下一项实际工作

先完成当前调用路径的两处离线工作，再新增模型请求：

- 在教师提议schema和唯一runner接通source_functions，显式提供真实初始source_program，允许C与Free同样学习确定性/组合来源φ；用当前已付费程序及原八母实际输入证明接口一致。当前compile_proposal的source_functions参数及observe调用已实现，**教师wire尚未启用**。
- 记录新来源程序输出相对共同输入哪些根保持、哪些新建/修改；legacy_root目前是上游事实的存储名称，render的retained_old_root标记尚需按实际程序/逐根来源校准，不能因keep_root就把新φ算旧流程，也不能把共享Free产物冒充C学习成功。

随后只用原八母已有TRAIN错误、部分源审查和代码进行真实更新，原c46f/96361结果不回流调双方。新增真实验证前固定原TRAIN后续来源并明确继承全部暴露/成本；不追加全局来源或种子，不重复旧冻结对照。当前既定C/U方向不变，不仅靠问句反复试，也不将接口接通当贡献成立。

U已有source/old-AST/new-AST共同typed参数、跨组件同一替换、歧义保持、有限守卫及条件编码；新位置法值须实际源绑定、明确复制或固定API常量。source_program已纳入同一候选入口。**实际φ/G更新字典、候选选用、负适用及独立迁移收益均缺**。旧Airline与de42同例被完整修复复用吸收，保持关闭，不继续扩展。

## 账本、公开与边界

唯一连续账本artifacts/rr_v2_preflight/research_ledger.sqlite3。最新终结 **10091行＝9869E/222T，在途0**，原9964行逐条保持。此轮新增125E/2T：执行器281400输入/11478输出token、356.653服务秒；教师557273输入/38657输出token（含15631reasoning）、725.527服务秒。执行实际wire全部thinking OFF/max8192；现金发票/GPU分摊未知。[逐请求](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_diagnosed_update/cost_and_preservation.json)。后续来源程序接入与等价检查模型新增0。

前一固定片段八母C20/32、NoFit20/32、Free23/32；旧后续两母C0/8、NoFit/Free2/8，全部保留。原9807行起该片段154E/3T及600秒超时、未知token/费用保持，不能与本轮新125E/2T混淆。

最近已核验公开快照为[96b816d](https://github.com/H00RU/LegalSkillGuard/blob/96b816ddeb9d975ce9ec72563c5c22947678a7c6/reports/legal_skill_evolution_run_20261111/method_investment_20261113/update_train_result.md)，对应较早C在途时；后续本地实现/证据已提交并将同步当前研究分支，main未改。恢复优先以这份本地状态和真实账本为准。

原128母/8批、七系统DEV/TEST、旧A/B/M1/M2/Lift/CoRev及反证完整保留；历史TEST已暴露，不用于当前修订或声称新盲测。此前网页偶然暴露记录保持，不作为监督。本轮只用既定原TRAIN，不启动新完整训练、DEV/TEST、论文；Goal未满足前保持active，不自行暂停或标记完成。
