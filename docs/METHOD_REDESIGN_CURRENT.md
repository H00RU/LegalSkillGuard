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

## 当前运行及下一项实质工作

`experiments/legal_skill_evolution_source_scope_repair.py`，run=`legal_skill_evolution_source_scope_repair_20261114`。只用上述8母中的de42、6fce两份原TRAIN进行有限源语义修复；不增加来源、不回放受保护的已评分复用，不改消费者/模型配置。两臂获得完全相同的两份全文、合法TRAIN监督、当前双方库与实际部分源审查，Free保留完整普通程序能力。C应真实连接局部成员/资格、父子动作和引用，不丢已有有用信息来制造G需求；错误旧项只能由实际法源依据修订，不能靠保留正确新项掩盖冲突旧项。

离线schema、完整程序传输回环及source hash均通过；请求约35万字符，小于上次约67万。串行教师正在运行，执行器计划0次，不重复启动。调用前账本10581＝10343E/238T；实时10582含C教师reserved1，主客户端PID3022060。恢复必须查真实PID、账本及call文件，旧PID只是身份线索。冻结manifest里的代码/协议/数据保持，观察只写非绑定文件。修复完成后先核对实际源语义、共同信息控制和使用路径，再决定后续，不沿原错误方式批量请求。

## U为何没有实证及当前检验任务

`joint_updates.py`和`joint_library_updates.py`已实现共享typed角色、源/前后AST绑定、跨组件编辑、歧义保持与有限守卫；**真实φ/G更新字典仍为空，没有后续正确实例化记录**。已有全局接口、arity/lambda、标点及证据传递修复不能冒充U。旧Airline/de42同例收益已被完整修复缓存吸收，保留关闭，不再重跑。

目前缺的是实际语义修订里的共同源—代码参数，以及相对直接完整修复复用的必要性，不能只称“尚待更多训练”。这次两母修复保存完整before/after和实际源见证，接着检验现有U表示能否抽出真实跨组件编辑，并与正确修复缓存/错误—修复检索/同信息普通更新比较。若当前generic程序修复没有源参数化需求或被强控制吸收，应据此调整U具体机制；不把这种结果包装成U成功，不再只累积C接口检查或继续空字典完整训练。

## 费用与保存

已终结源获取阶段10579→10581：0E/2T，原10579行逐条hash保持；356915输入、43894输出（含22023 reasoning）token，826.159教师服务秒。编译适配、8母实际代码执行、共享消费者、下界证明和证据修复新增0调用。现金发票/GPU分摊未知。[逐请求与保存](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_gap/cost_and_preservation.json)。正在进行的scope repair调用独立追加，不混入上述终结费用。

原完整128来源8批与七系统DEV/TEST、旧A/B、M1/M2、Lift/CoRev、MAUD四/二母、12/4、两母源原子及冻结复用结果均保存，旧测试暴露不指导当前修补。2母冻结复用虽然双方8/8，删新增G仍8/8，不能认定迁移。旧24/48等分数及失败不重新命名为当前方法成绩。[完整历史结果与当前报告](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/update_train_result.md)。后续只更新本文件的当前状态，不恢复历史执行队列。
