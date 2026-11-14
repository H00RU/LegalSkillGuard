# 当前证据与下一项实际工作

2026-11-14。同一Goal **active、未完成**。目标、验收、资源授权及边界只由[CURRENT_GOAL.md](CURRENT_GOAL.md)规定。唯一项目`/home/yndx/hhy/legal-skill-current`，开发分支`repair/lift-corev-activation-20261112`，main不改。旧Goal卡、暂停消息和历史下一步不构成队列。

## 当前结论与真实进展

最新固定8母源获取已完成两个独立真实教师调用；双方学得完整源程序，在同样原TRAIN与原评分上执行。C从先前15/32变为25/32、Free从17/32变为21/32。C实际可执行25/32，Free24/32；未覆盖分别7/32、8/32，没有fallback物理调用，全部保留分母。这是获取训练结果，不是新盲测或整体语义认证。共享C消费者、保持Free类型和实际法律项不变时为23/32；其中8fb跨消费者损失1题涉及表示兼容，不能把这项控制简单当作全部同条件获取优劣。

|固定原TRAIN母来源|C正确/4|独立Free正确/4|
|---|---:|---:|
|e7b7|4|3|
|de42|4|3|
|5cad|4|4|
|a5b0|2|0|
|62fd|2|2|
|bbb3|4|4|
|8fb3|1|1|
|6fce|4|4|

[逐来源、原生答案和实际使用根](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/source_results.json)、[原始响应/完整科学提示与源码](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/artifact_copy_manifest.json)。两臂操作均为空，实际源/G/消费者是确定性程序主路径，不需要增加弱执行器调用。

## C的证据和已定位缺口

- e7b7原文34确有Agreement结束或请求触发、立即返还/销毁；C新程序取得，Free仍用request-only旧规范。这是明确的源获取改善。de42及a5b0的部分分差由消费者解释吸收，不能算全部为C算法收益。
- 当前24开关G在最后6fce枚举超时555理论，原超时保留。其他已完整枚举的正损失来源最低错误2、2、3；其余来源建议G已经0错。建议G达到全局错误下界7且选择编辑0，故可严格认证不变最优，无需完成最后枚举；不冒称运行了整个选择求解，不证明源语义或方法贡献。[精确证书](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/certified_revision/certificate.json)。
- 证据传递存在工程缺陷：root_support(A,U)让整份联合证据被输出为各个单U。公共确定性适配把仅用于证据的U坐标换成实际term A、support_from_terms；所有规则body/cost、源代码、法律模板、选择保持。8母法律项集合、答案/正确与覆盖保持25/32，6fce处置证据恢复[15,16,18]；不合并不同见证的同项、不补入未取得条款。20坐标修复、10项相关回归通过。[实际修复重放](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/unbound_provenance_replay/proof.json)。这是工程修复，不计U。
- 真正的源遗漏仍在：de42新项只引39，缺40/41的三个月非成约与prompt请求分支证据/期限；6fce缺20/21的Agreement结束/书面请求返还，10/12的Representatives定义与书面保密资格尚未连接，61义务主体/确保affiliate履行的关系被扁平化。两臂都保留了上游15的错误“请求下返还或销毁、无例外”旧项。原生4/4不能认证这些字段已正确，不把全字段完美新增为安装门槛。

## 最新两母定点修复已终结，候选不直接部署

`experiments/legal_skill_evolution_source_scope_repair.py`，run=`legal_skill_evolution_source_scope_repair_20261114`，串行两个真实教师已完成，无executor请求。仅用上述8母的de42/6fce修复，其他6母为预先固定的原TRAIN保留检查，历史暴露披露，不称新盲测。两臂全文、TRAIN监督、当前双方库与部分源审查相同，消费者冻结。

|范围|C修复前→候选|Free修复前→候选|
|---|---:|---:|
|两母修复，原生正确/8|8→8|7→7|
|其余6母保持，正确/24|17→13|14→13|
|总计正确/32|25→21|21→20|

C真实取得了独立action/trigger/exception/责任/披露资格原子和共享scope/actionID连接，20规则/18建议；新Norm都由G产生。6fce错误上游“请求下任选返还销毁”已删除，20/21协议终止返还取得，10/12书面资格在员工/顾问/代理三类真实Norm上连接；61代履行与引用明确保留、未展开细节仍unresolved。de42两个触发分支有39/40及39/41联合支持，三个月以原文触发限定保留，不称已完成数值计算。6fce删除资格连接4→2、删除处置连接4→3，de42仍靠旧根保持4。局部检查不认证全源所有字段。[实际干预和部分源审查](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_scope_repair/unbound_C_actual_mechanism_and_partial_review.json)。

整模块替换同时丢失C原e7b/a5b/8fb能力，不能把局部修复当整体升级，也不能用旧流程fallback掩盖。Free原提议引用任务中已提供的5个C原子却漏自身schema声明；确定性恢复只逐字导入既有类型/含义，源/组合/H不变，原失败/编译保留。[全部保留结果](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_scope_repair/source_results.json)、[完整响应与源码](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_scope_repair/artifact_copy_manifest.json)。

该阶段结束时累计10583＝10343E/240T，旧PID3022060已终结，不重启。最新结算见下文U。manifest source/data、原10581条账本hash均保持。保留两版库及候选，原八母25/21结果不覆盖。该阶段的U下一步也已按最新用户要求退役，停止用整体重写继续凑修订样本，不启动完整训练/DEV/TEST。

## U历史研究资产：影响范围学习与同信息否定证据

前一轮用户补充保持C，要求U从**真实修复和跨来源误改反馈**学习：哪些法律依赖应改变，哪些仍有效的原结论应保持，并实际约束后续编辑生成与选择。法源绑定、参数和guard只是执行支撑。旧答案如有法源反证须允许撤销，不把历史答对机械变成不可变约束。目标与验收保持原要求。

刚完成零调用的局部退役原型：从原de42/6fce两个修复母来源与e7b来源的已知正确能力构建203个真实源/程序绑定候选，用实际5条错误证明与明确保留见证选出2条策略。实际执行原生25/32保持，错误源Norm5→0，实际使用错误Norm的答案路径5→0。另5母在策略冻结后执行，触发0，不能声称跨来源更新成功。两种强简单控制（全精确条款覆盖、末尾声明引用字段覆盖）同样25/32及5→0，效果被吸收。该原型保留为确定性维护资产，**不算U独立实证，不扩展同一实例**。原learned_U、原始DP原型和修正、所有结果均在`artifacts/legal_skill_evolution_bound_edits_20261114`；旧AST核心及全部否定证据保持。

这次范围检查还发现新φ4仅在修补的两母产生新原子，其他六母均0；这限制了当前U可验证的后续适用机会。不能据此新增“每源都要新分支”的门槛，也不能用未触发来源充当迁移成功。C保留，未启动完整训练。

**历史U实现：修订影响事件与执行约束（不再作为当前队列）。** 合并既有真实证据，而非造错误案例：e82b不同动作的材料/触发修复；6fce资格与动作责任、de42期限修复及整模块改动误伤e7b/a5b/8fb；MAUD目标角色修复中仅改renderer导致12→10、同步解释器恢复12的真实联动记录。全局同一库更新跨母应用不重复计为多个独立修订事件。源字段未知、未审查或旧答案碰巧正确不标成必须保持。

实现先形成带证据的法律依赖/程序依赖与影响标签，学习可改变、必须修复、应保持及需重查的范围；将它们传入编辑生成、组件联动与候选选择。范围约束保护的是仍有效的法律结论/语义，不固定旧AST或接口。必要强控制包括通用最小编辑/静态依赖切片、同信息正确修复缓存、源图统一闭包及绑定型U；不把额外人工监督只给ours。

当前已实现`repair_impact_learning.py`、约束接口及真实编辑调用路径。学习对象是有来源/代码见证的依赖路径和当前字段形状上的`must_change/preserve/recheck`规则，复用原精确DNF/set-cover核心；只用正向可见谓词，避免把部分图缺边当反证，未审查不补负标签。源合法性与执行仍独立检查，预测不是法律证明。

**一次真实同信息配对已完成。** 用旧3父修订、28条监督学得V1，将其范围真正放入编辑请求，修复原八母中62fd的“带例外规范＋无例外副本”真实问题。FreeHistory获得相同原文、真实历史/图/反馈、底座和联合修改能力，独立编辑。双方都编译并走真实主路径，删除错误副本且保留带例外规范和主体；八母均25/32→25/32。ImpactGuided改5个source函数、Free改4个；此次没有U额外准确率或成本优势，不扩展同一副本删除例子，不把接口打通当贡献成立。[真实配对](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_impact_guided_edit/README.md)。

实际反馈继续进入离线学习：原4条跨源Native误改来自3母；逐一审查原文后取得4条法律字段保持见证，保护e7b终止/请求触发、a5b主体/同意例外、8fb请求/空白期限，不把旧答案当法律真值。补齐原先已明确的必要修正监督后，V2为3父/50标签。随后在本次真实配对发现两个同源条件字段的图特征完全相同，却一条应保留、一条应修正；字段已有的`add_exception/no_exceptions`程序形状未进入观察。最小补入真实名义构造子，并把实际修复当后续TRAIN反馈，V3为4父/60标签，三类策略均可识别，训练监督无冲突。[学习与真实反例修正](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_impact_scope_learning/README.md)。

须区分：真实配对使用V1；V2/V3是随后离线反馈更新，未重跑或改写配对结果。V3尚无后续独立真实编辑证据。部分规则仍可能只是共同修复中的共变，不能写成已经发现因果依赖；当前源检查和有效结论约束继续决定候选是否可接受。47项相关回归通过，不替代方法收益。

## 当前第二方向：正确技能的实例化与执行，C保持

用户最新明确希望尝试解决“律师拿到正确技能仍做不对题”；第二研究方向据此调整，U不再作为第二贡献主线，代码/原始结果/否定证据完整保留。不是新Goal，也不新增来源、模型配置、主训练或TEST授权。

已有历史症状可复用：11月5日原32源上下文诊断中，21条新错金额有13条超过原事实资产值，包括18元袜子填600；原技能已规定不超过资产值。此前已有原文锚定执行示范、程序数值技能、强制算术、同库位置/编码、局部源绑定等尝试，不能再把这些当未经尝试的新方法。这些是历史诊断，不冒称当前128池的新增结果。[历史事实绑定证据](reports/EV_OWN_EC_CONTEXT_DIAGNOSTIC_20261105.md)、[旧执行示范设计](research/OPENEXEMPT_CODE_GUIDED_EXECUTION_REPAIR_20261028.md)。

刚核查的直接近邻包括[SkillSentry](https://arxiv.org/html/2608.09253v1)：技能规范与成功/失败轨迹生成DSL运行时指导，按步骤检查和更新指导；[SkillAligner](https://arxiv.org/abs/2608.06880)：执行前联合适配技能；[Faithful CoT](https://arxiv.org/abs/2301.13379)、[SatLM](https://arxiv.org/abs/2305.09656)及[BINDER](https://github.com/xlang-ai/Binder)已有符号/程序执行与神经接口。因此泛称“正确技能＋执行监督/编译”不够作为差异。当前不宣布新方法已成立。

已开始零调用原TRAIN定位：原Full八批280视图中37实际走技能核心，31个非完全正确视图来自21母，仅作为待审候选；已剔除2条SARA实际§3306(b)技能运行于§3306(c)问题的作用范围错配，不当作“正确相关技能执行失败”。当前原池的正确技能执行失败集合尚在核验，历史18元→600只作问题证据。[当前方向、近邻与候选原始索引](../reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/README.md)。

**当前已落实的第二方向最小实现**：原真实付费记录确认§3306(c)(5)(A)程序和法源常量正确，8B已收到明确雇主/雇员，仍将“Bob是Alice的父亲”直接填为“雇主相对于雇员是father”。固定原程序的子女两种关系视图均得到同一正结论；这是零调用源码审查与重放，普通关系投影也能修好，不能作为独立贡献。[逐字段原始证据](../reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/verified_source_frame_error.json)。

已实现`case_observation_contract.py`：学习案件观察schema及纯事实适配程序，法律核固定；每个带当前原文见证的相容参数赋值都实际执行，有相关未知/分歧/未覆盖则保持unresolved。类型、quote及结果一致不自动认证事实覆盖。24项相关回归通过。共同法源核取得与一次明确源/接口修复共2T：修正跨年20k门槛不能跨年相加、原生有限案件与神经未读取的区分；共享日历函数接口修复公平开放。原坏程序、软件反例和修改后回归完整保存，未派发坏核给8B。

固定原TRAIN三母`3e22604a20/d9d6b23646/5c29a3a22f`，分别为亲属方向、工资事件、居住时间。第一母真实错误提供获取反馈，后两母只给教师法源/固定核，不给案件事实或标签；三母均为历史暴露TRAIN，不称新盲测。两臂教师独立获取、信息与观察/适配容量相同，强Free可使用关系投影、程序、历史正确修复与歧义；DirectRead将共享同一正确核与反馈。静态普通关系投影已恢复首母，应单列该简单控制。未来两母核的法源获取不算从首母学会迁移。

**三母真实小试已经终结**：ProgramGuided 3/3、独立FreeHistory 3/3、DirectRead 2/3；两学习臂2E/臂，DirectRead 3E，共7E。DirectRead在相同正确核和真实错误—修复反馈下仍填反father，公共范围检查使其unhandled，不用fallback代答。两学习臂实际工资归属和时间裁剪均正确；首母关系投影被Free及静态关系控制吸收，当前专门机制没有独立增益。相关未知保持、两种关系备选的一致执行已真实使用；分歧澄清、多轮更新及C联合收益尚无实证。不会继续重复这三母或把3/3当整体通过。[完整真实结果、算法、原始请求/响应与费用](../reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/real_observation_pilot/README.md)。

**下一项实际工作**：复用当前可运行观察契约底座，只读C现有源程序及同库不同消费者记录（已零调用保存4条差异，尚非4条已认证错误），隔离“法源法律项正确但案件/查询实例化错误”的实际路径，再围绕该断点验证规程学习；不把已取得核定义的两母成功称为从首母学会新规则或迁移贡献，不把通用程序投影包装为新机制。常规研究自主继续，仍限原TRAIN与有限比较，不启完整训练/DEV/TEST。当前无研究客户端/模型请求，原PID3326259、3337575均已终结；连续账本10596＝10350E/246T，在途0。Goal active、未完成。

## 费用与保存

已终结源获取阶段10579→10581：0E/2T，原10579行逐条hash保持；356915输入、43894输出（含22023 reasoning）token，826.159教师服务秒。编译适配、8母实际代码执行、共享消费者、下界证明和证据修复新增0调用。现金发票/GPU分摊未知。[逐请求与保存](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/cost_and_preservation.json)。两母scope repair另新增0E/2T，201230输入、34826输出（含17724 reasoning），675.810服务秒，原10581行保持。两阶段共0E/4T；该截面累计10583。[两母费用与保存](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_scope_repair/cost_and_preservation.json)。

原完整128来源8批与七系统DEV/TEST、旧A/B、M1/M2、Lift/CoRev、MAUD四/二母、12/4、两母源原子及冻结复用结果均保存，旧测试暴露不指导当前修补。2母冻结复用虽然双方8/8，删新增G仍8/8，不能认定迁移。旧24/48等分数及失败不重新命名为当前方法成绩。[完整历史结果与当前报告](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/update_train_result.md)。后续只更新本文件的当前状态，不恢复历史执行队列。

本次范围学习配对另新增0E/2T，219387输入、7722输出（含4868 reasoning）token，167.902教师服务秒；累计10585、在途0，旧10583行逐条hash保持。实际现金/GPU分摊未知。V2/V3离线反馈和全部执行检查未新增调用。费用和逐请求见[本次配对费用与保存](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_impact_guided_edit/unbound_actual_check/cost_and_preservation.json)。

本次正确技能观察契约小试新增7E/4T：共同法源核及源/接口修复2T，独立两臂契约各1T；教师81202输入/37476输出（含23466reasoning）、732.454服务秒，executor30674输入/2998输出、87.408服务秒。原10585行hash保持，所有请求终结，无失败/重试或DEV/TEST调用。现金发票/GPU分摊未知。[本轮逐请求与保存](../reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/real_observation_pilot/cost_and_preservation.json)。
