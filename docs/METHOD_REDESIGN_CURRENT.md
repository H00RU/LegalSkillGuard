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

当前无模型客户端/在途，真实旧PID3022060已终结，不重启；累计10583＝10343E/240T。manifest source/data、原10581条账本hash均保持。保留两版库及候选，原八母25/21结果不覆盖。下一项实质工作见下节U，停止用整体重写继续凑修订样本，不启动完整训练/DEV/TEST。

## U为何没有实证及当前检验任务

`joint_updates.py`和`joint_library_updates.py`已实现共享typed角色、源/前后AST绑定、跨组件编辑、歧义保持与有限守卫；**真实φ/G更新字典仍为空，没有后续正确实例化记录**。已有全局接口、arity/lambda、标点及证据传递修复不能冒充U。旧Airline/de42同例收益已被完整修复缓存吸收，保留关闭，不再重跑。

两母修复已经留下真实before/after，但每臂只有**一份整体库更新应用于两母**，不是两个不同参数化局部编辑。源—代码角色对应尚未取得，不能从整体泛型程序直接宣称归纳出了U。这是学习事件/编辑粒度未打通，不只是训练不够。[实际事件诊断](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_scope_repair/unbound_U_actual_event_diagnosis.json)。

**下一项实际工作：**在现有真实修订及源见证中分离局部语义编辑，核对共同参数与代码位置，接现有typed AST核心得到真实U；同信息完整正确修复缓存与普通自由更新继续作为强对照。如果实际局部编辑没有源参数化必要性或效果被其吸收，依证据处理U具体机制，不把一般代码保留、整模块选择或旧流程回退冒称贡献。不得为凑U制造错误程序、删已有字段或额外造来源。当前未验证U额外作用，Goal active；不以报告、部分满分或软件测试完成。

用户要求的[两项方法详细报告：问题、算法、实现、真实证据与未完成部分](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/TWO_METHODS_EXPLAINED_20261114.md)已写入，当前定位和算法说明以该报告与CURRENT_GOAL为准，不增加方向或新验收门槛。

## 费用与保存

已终结源获取阶段10579→10581：0E/2T，原10579行逐条hash保持；356915输入、43894输出（含22023 reasoning）token，826.159教师服务秒。编译适配、8母实际代码执行、共享消费者、下界证明和证据修复新增0调用。现金发票/GPU分摊未知。[逐请求与保存](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/cost_and_preservation.json)。两母scope repair另新增0E/2T，201230输入、34826输出（含17724 reasoning），675.810服务秒，原10581行保持。两阶段共0E/4T；累计10583、在途0。[两母费用与保存](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_scope_repair/cost_and_preservation.json)。

原完整128来源8批与七系统DEV/TEST、旧A/B、M1/M2、Lift/CoRev、MAUD四/二母、12/4、两母源原子及冻结复用结果均保存，旧测试暴露不指导当前修补。2母冻结复用虽然双方8/8，删新增G仍8/8，不能认定迁移。旧24/48等分数及失败不重新命名为当前方法成绩。[完整历史结果与当前报告](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/update_train_result.md)。后续只更新本文件的当前状态，不恢复历史执行队列。
