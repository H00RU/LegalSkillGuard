# RR-v2 主训练就绪结论复核 — 2026-11-06

**建议：先修复两个具体工程阻断，再决定启动主训练；撤回此前“已具备主训练条件”的结论。** 阻断是 A 的分离批次内核尚未接通真实文本入口且成本单位不符，以及共享接口的发送 schema 与解析器不一致。不是因为存在16条回退、任务准确率不足或缺少所有分支的线上样例。本次仅复核和保存证据：新增 executor 0、teacher 0、oracle 视图0，没有启动训练或正式评测，也没有修改科学实现。

依据为[原服务器交接](legalskillguard_server_handoff_v2.md)的“本次必须完成的实现”“离线检查与有限真实预检”“完成条件”，以及[原方案 §3.3、§4.3](legalskillguard_rule_reasoning_plan_v2_20261105.md)。后续授权已取消旧轮次、首错停止及100/2预检子上限；本次用户要求不新增模型调用优先。原研究6000/20总账不变。本复核不增加零回退、20/20答对、所有分支实测、候选H必须缩小或涨分门槛。

## 1. A：稳定分支成立，残余及分离批次的证据需要拆开

| 环节 | 现有真实流程证据 | 离线证据及其边界 | 判断 |
|---|---|---|---|
| 原文登记、受限公开文法编译、允许补全集与稳定检查 | 原固定ProofWriter index 3、8、13、18各有一次新真实请求，经共用 `ingest_source → analyze → parse_public → completion_theory → complete`；答案依次Unknown、False、False、Unknown，与对应参考语义一致 | 原始请求、执行记录和独立重放均保留 | 这4条是有效A主路径成功，不是fallback或默认标签 |
| 相关未译例外、无关残余、TOP/空Ω/冲突/域外/超时 | 上述4条全部 `residual_count=0, batch=[]`；没有非零残余的真实成功记录 | 原离线微例确实证明：已核无关残余可稳定，相关残余会阻止稳定；冲突/域外/超时不伪装成Unknown | 有效内核检查，不能描述为4条真实请求已验证这些分支 |
| 异答分离、XOR联合批次、上下文闭包 | 4条真实请求没有调用非平凡的分离批次 | 有效有限域XOR微例选`s1+s2`，共享上下文`s0`只计一次，测试成本13；路由测试注入预先算好的assessment，验证了消费端 | 求解内核与消费端存在，但生产端连接缺失 |

具体缺口在[public_horn.py](../legal_skill_guard/rr/public_horn.py) `assess` 与[engine.py](../legal_skill_guard/rr/engine.py) `analyze`：无残余/已经稳定直接返回；有任何查询相关残余则保守全量返回 `conservative_full_source_no_separation_claim`；否则残余域全是单值`no_effect`，没有需要分离的异答世界。其他数据集的通用入口只在残余为空时构造有限理论，没有产生带完整语义观察的残余理论。当前生产路径因此不能产出非平凡的、分离完备的选择结果。测试中的手工 `FiniteTheory` 与注入批次不填补这一接口。

保守全量读取本身符合允许fallback，不能把TOP的粗答案影响槽冒称完整条款语义观察。但现有代码把所有有用的非平凡选择都挡在生产入口外；这是原方案要求的实现尚未接通，不能仅以“尚无全分支线上记录”解释。

另一个确定缺口：`analyze`传给`assess`的是 `lambda ids: len(ids), 32768`，计条款数而非原§3.3要求的一次调用开销加条款及上下文闭包token。客户端的整体上下文token保护已经存在，却没有进入批次优化成本。离线人工成本函数验证的是内核参数能力，没有验证真实成本连接。

最小修复应将已验证的完整观察/域契约接到共用生产入口，并将实际序列化输入的token计数、固定调用开销和共享上下文去重接到规划器。没有可靠完整观察时继续保守全量或未决，不生成假语义。先用已有人工XOR/残余微例从生产入口贯穿到第二次解析动作；不要求新增基准来源，不要求自然语言的所有分支真实命中。

## 2. B：真实碰撞细化及执行成立，覆盖范围有限

4个原ProofWriter来源实际执行 `ingest_source → learn_source(trace=...)`；没有把缓存学习结果当新学习返回。参考标签仅复用原已计数的来源及oracle缓存；连接图预测在当前运行中实际执行。粗接口同值异答碰撞分别6、4、6、6对，共22对；细化后的`entity_equality`可区分这些碰撞。每来源原实例加4个视图，共20次实际连接执行与参考语义检查一致。[独立证据](rr_v2_evidence/semantic_preflight/core_acceptance.json)、[逐字重放](rr_v2_evidence/semantic_preflight/core_wire_compatibility.json)保留。

候选H数量为8→8、10→10、8→8、8→8。原先检查器错误地附加“H必须减少”，已撤销这个非原方案条件；原始False检查结果和候选数未删除。碰撞被细化字段区分且实际图执行正确足以支持这些样例；不能因此宣称唯一识别连接或H等于Ω。

实体见证join有真实主路径证据；逐项/整体cap、共享额度不复制、守恒但分配次序影响答案、不可恢复见证等有相关离线检查，没有被宣称真实全部覆盖。其余16来源中，9条只有字段模式（8个OE/RA的membership、1个SARA的entity_equality），3条没有可接纳模式（历史参考失败1、有限搜索未观察碰撞2），4条ContractNLI无oracle。[source_learning.py](../legal_skill_guard/rr/source_learning.py)当前只为ProofWriter构造可执行Horn连接候选；OE/RA字段约束不能算已验证的数值连接器。图为空/无候选必须保留未决或按设计回退。

**比例口径纠正：** A最终任务回退为16/20（80%），其中6条native答对，不算核心成功。B已核验可执行主路径为4/20（20%）；其余16/20是“缺少已核验可执行连接”，不是另一次测量得到的B预测fallback率。4条B真实连接验证本身fallback为0/4。字段模式仍可以作为后续提示约束，不能冒充连接执行通过。原方案允许无候选回退，不要求每库都有正例，因此这一B覆盖边界单独不构成必须额外增加实测的门槛。

## 3. 其余16来源逐项归因

索引沿用原固定20来源顺序；完整ID、原始record路径、程序状态、错误和usage见[来源审计JSON](rr_v2_evidence/readiness_review/audit.json)和[原来源状态](rr_v2_evidence/semantic_preflight/source_status.json)。表中“回退正确”不计A/B成功。分类可重叠：按设计回退与模型/工程问题并不互斥。

| index / 数据集 / ID前缀 | 原始结果与原因 | 分类及剩余影响 |
|---|---|---|
| 0 OE `4f3b7eff8dad` | IR可执行；EC/EV资产、引用及金额不完整/错误，无完整源语义证书；B仅membership | 模型语义错误；B字段级边界，无全局运行阻断 |
| 1 RA `e88c2c8f441b` | 先前native/IR1163，参考1433；最终`finish_reason=length`且JSON为空 | 模型错误及固定输出预算截断；不得补全缺失输出，失败计入流程 |
| 2 SARA `815f377b6412` | native Contradiction，参考Entailment；IR以节号自等恒真给Entailment且源链接不当；一次历史oracle stdout为空，另3视图成功 | 模型错误＋已修复工程故障的来源级残留；该失败视图仍收费/隔离，不重置四视图计数 |
| 4 CNLI `d9360f2a8c03` | native NotMentioned正确；接口字段形状被解析器拒绝 | 本来允许native回退，另有模型格式错＋未解决schema/解析契约不一致 |
| 5 OE `fe5acb6c9806` | 只输出部分资产/引用，完整任务不匹配，B仅membership | 模型遗漏；非运行崩溃 |
| 6 RA `9b47bd06b2ac` | native3735、IR885，参考3695 | 模型规则/费用计算错误；B无可执行连接 |
| 7 SARA `8175fcb9abeb` | native Entailment正确；IR用节号自等作恒真规则，源段不支持；B有字段无图 | 模型IR语义错误，native回退正确；不能算核心成功 |
| 9 CNLI `e671a984356f` | native NotMentioned正确；unsupported附带的接口形状仍不符合解析器 | 允许回退＋模型格式错＋同一工程契约缺口 |
| 10 OE `ae1e4bdb9abb` | 法条引用/资产金额错误；第一IR无效，第二可执行但任务不匹配 | 模型输出/语义错误；B字段级边界 |
| 11 RA `92d91f15d181` | native3518、IR3035，参考3418 | 模型规则错误；非执行器异常 |
| 12 SARA `5c29a3a22f75` | native及IR Entailment，参考Contradiction；字面值溯源通过但规则逻辑错误，4视图未发现碰撞 | 模型语义错误；无已观察碰撞时允许不细化，不证明全域无碰撞 |
| 14 CNLI `354623271a54` | native NotMentioned正确；接口字段形状错误，graph为列表 | 允许回退＋模型格式错＋同一工程契约缺口 |
| 15 OE `cdf5d6eb5caa` | 两次均length，最终字符串未闭合，无有效完整native输出 | 模型在固定预算内截断；不是已修复的旧解码器引号问题，不能靠适配补语义 |
| 16 RA `575fd48cab69` | native/IR1130，参考1110 | 模型费用规则错误；B字段级边界 |
| 17 SARA `097568705cac` | native Entailment正确、IR Contradiction错误；无合格反事实视图，未发现碰撞 | 模型IR错及搜索覆盖边界；native回退正确，未获连接证据 |
| 19 CNLI `442c36c12745` | native NotMentioned正确，`unsupported_no_certificate`，interfaces为空 | 纯预期回退；无正式NLI语义oracle，不制造反事实标签 |

SARA历史失败不是四次oracle全失败，也不是当前整库不可运行。[原输出flush对照](rr_v2_evidence/sara_original_flush_control.json)重复显示：原参考程序不flush退出会空stdout，加flush正常输出Entailment。当前`evaluate_sara`已加`flush_output`；原失败记录保留且占额，同来源另外3视图及其他SARA视图已有成功记录。现有证据支持此工程缺陷已修，不支持擦掉失败或额外越过来源级视图上限。

新增发现的共享契约缺口可以直接重现：通用`PROPOSAL_SCHEMA.interfaces.items`允许任意object，但`analyze`要求精确`fields/graph/bindings`。实际index4/9/14都通过发送schema、随后被解析器拒绝；index19合法空接口正常进入预期回退。[完整字段证据](rr_v2_evidence/readiness_review/contract_mismatch.json)、[复现脚本](rr_v2_evidence/readiness_review/contract_audit.py)。应收紧发送契约使之与解析和执行要求一致，保留合法空接口/unsupported；不能接受字段别名、将graph列表随意转换或补造缺失绑定来改判旧结果。

## 4. 是否系统性阻断其他四库正式流程

**没有证据表明16条失败都会使正式循环中断。** 本次禁网络/子进程，以保存的真实原文字符串作为mock回调，对16来源×六臂做96次控制流重放，全部完成，每条走固定三次上限及fallback，冻结库未改。第3次回调复用最后一条旧响应，只用于检查异常处理与预算控制；这不是新增真实预测、真实三次调用结果或质量证据。[审计及全部重放](rr_v2_evidence/readiness_review/audit.json)、[代码](rr_v2_evidence/readiness_review/audit.py)。既有144项相关离线通过记录仍有效，本次未扩张正式评测矩阵。

| 库/共用机制 | 流程可继续的证据 | 仍需处理或保留的边界 |
|---|---|---|
| OE、RuleArena | IR可执行/模型错误均记录；失败不漏计，回退与六臂控制流可完成 | 本轮不能宣称数值法律语义/数值连接正确；membership字段不能当执行图 |
| SARA | 当前参考调用带flush，多条视图已成功；无模式/参考失败分支可恢复 | 旧失败来源的监督缺口保留；不得重新查询以抹除失败 |
| ContractNLI | 无oracle明确允许native fallback；空接口可用，原生结果保留 | 3条真实响应暴露发送/解析契约缺口；虽然被捕获不崩溃，会系统性损失接口学习机会 |
| A共用路径 | 保守全量/未决可避免伪证书 | 其他四库没有可用残余观察规划入口；即使循环能跑，也不能称原要求的A选择机制已完整实现 |

因此，阻断是**方法实现与契约完整性**，不是要求其他四库在预检就高分或零回退。B的范围限制、无碰撞和合法NO_VALID_CONNECTOR本身可如实进入后续研究，不追加“每库至少一次B真实成功”等条件。将A缩减为始终全量翻译会改变原方法；若不修接口而走这个方向，需要研究方案调整，不能默认为本轮已获授权。

## 5. 最小下一步与验收依据

1. 离线修复A生产入口到完整观察理论/分离规划的连接及真实token成本；使用现有人工XOR、相关/无关残余、上下文闭包和保守TOP微例走共用生产调用链。验收是可达性、分离正确性和成本口径，非新增质量要求。
2. 统一五库接口外层schema、提示示例、解析器和执行器约定。用已保存3条坏接口、1条合法空接口及现有合法连接做回归；原错误原样保留，禁止补造字段语义。
3. 针对实际改动重新跑必要离线检查及同账免费恢复，生成新代码绑定；不得让当前旧binding准备凭据替新代码背书。只改本范围调用路径，无需大重构或新数据。
4. 若发送到模型的契约发生变化，后续在解除本次“零调用”约束后，建议最多**2次executor、0次teacher**：原CNLI受影响来源1次验证接口契约，另一个原固定来源1次验证修改后的共同入口及来源语义/正确回退。每次对应明确修改和离线证据；若首条已覆盖同一修改而第二条无独立目的则省略。额度仍扣原研究6000/20，不申请新增总预算。人工XOR的真实性来自离线完整链条，不强行诱导线上命中非平凡残余，不要求每个分支实测。本次没有执行这两次建议。

以上属于实现补齐，不需要改变A/B研究问题、数据、模型、seed、thinking、评分或原验收。无需为修掉10个模型错答继续反复请求；若修复后仍是忠实性未决，按原方案回退并单列。完成上述两个阻断的最小验证后可以重新判断训练就绪，不能将当前复核报告当作训练启动许可。

## 6. 保存、预算与状态

本次数据库完整SHA256及calls/meta/oracle逐表哈希前后一致；累计executor124，teacher3（2成功、1失败），全部结算，reserved0，oracle记录50条。既有Qwen服务PID958223、startticks486445918保持不变；没有新预检客户端。新增模型现金支出0；旧费用、token及时延不重新估算，见[原逐请求账本](rr_v2_evidence/semantic_preflight/request_ledger.csv)与[原费用摘要](rr_v2_evidence/semantic_preflight/summary.json)。

原预算静态核算仍可容纳后续计划：已用124E，剩余训练最多216E，后续开发864、冻结测试3456、B1 576、固定诊断384、native192，共5688；总计5812≤6000，原恢复桶余184。teacher已有3，剩7批每批最多2次时总计17≤20。本次不调用这些后续阶段。不是预算不足导致本次“不就绪”。

科学代码绑定仍为`47cddfaed75c295bf7655a7a2167e940db85c7c2b7520625a9534e746baa6b14`；实现提交`ba1eded37986fa67be74d4578ce26ed129ebd700`，复核前HEAD`dcf43c4`。本次只新增审计及更新状态文档；原始响应、失败、分数、SQLite、冻结库、科学代码及已有封存准备凭据均保留。[复核基线](rr_v2_evidence/readiness_review/baseline.json)及[前后哈希](rr_v2_evidence/readiness_review/audit.json)。

旧`formal_readiness_core.json`证明当时工件绑定、恢复及4条核心样例一致，未证明A生产规划入口完整，也未发现通用schema缺口；不覆盖本次提出的阻断。旧“已就绪”报告及状态另存`rr_v2_evidence/readiness_review/prior/`，当前决策改为`formal_training_ready=false`。Goal工具此前的complete是历史操作记录，本次工具不提供重新置active的接口；不另建或重启Goal，不将旧complete当工程验收已通过。当前工程目标仍未满足，正式开关保持关闭。

所有本次提交限`research/legalskillguard-rr-v2`；远端公开分支同步实现与证据，main不改。公开导出延续现有发布规范：保留科学记录，省略私人对话、账户/主机操作日志及环境。原始本地历史不重写。发布验证清单记录内容映射和不可变链接。
