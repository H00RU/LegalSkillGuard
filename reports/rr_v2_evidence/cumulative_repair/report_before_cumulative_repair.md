# 最新规则及契约修复验证（进行中）

用户已取消旧修复轮数和首类型失败停止条件。当前账本85 executor、2 teacher，无未结算请求；累计上限96，不重置。真实失败契约核查与130项离线检查、12来源×9个解码器用例通过，尚未新增真实调用，主训练未就绪。当前证据：reports/rr_v2_evidence/cumulative_repair/contract_audit.json。下文旧停止结论仅适用于被替代的历史策略。

---

# LegalSkillGuard RR-v2 实现与有限真实预检报告

更新：2026-11-06。Goals工具状态已在新周期第三轮阻断核验后设为blocked，目标未完成，结束自动接续。**第二轮在首个请求触发停止条件；完整goal未完成，尚未达到主训练就绪。** 用户允许的12次新增请求实际使用1次，余下11次保留且未发送。累计executor **85/100**，teacher **2/2**，本轮teacher新增0；没有启动主训练、正式评测、冻结测试或论文写作。

开发目录`/home/yndx/hhy/legal-skill-rr-v2`，分支`research/legalskillguard-rr-v2`。第二轮实现提交`ecd0ea8`；授权原文及hash在`docs/rr_v2/round2_user_authorization.json`。本地两份执行协议的允许修复轮次均已同步为2，旧账本没有重置。

## 第二轮修复前的36条原始输出审计

| 原始程序内容 | 条数 | 可确定性恢复的范围 |
|---|---:|---|
| expression缺少query | 25 | 可以规范数字或字段别名，不能补造查询 |
| expression已有query但分支残缺 | 2 | 不能推测缺少的条件分支、返回值或来源关系 |
| 不完整输出，wire均为length结束 | 4 | 不截断后拼接语义，不把中间思考当最终程序 |
| 显式unsupported | 5 | 保留未支持状态，不强制伪装成可执行程序 |

合计36条。仅对明确的整数/布尔/字符串表示、固定接口字段别名和显式literal包装做47处可逆格式适配，保留原文和逆向还原证据；恢复可执行IR为 **0**。适配过程未加载评分标签，未合成query、条件分支、来源链接或答案。记录：`rr_v2_evidence/strict_contract_round2/raw_recovery_audit.json`。因此不能把所有无可执行结果都归因于字段名称，缺失的程序语义是真实阻断。

停止真实调用后，以同一适配规则补充核查全部原84条executor原文（40对照+8首轮修复+36小试），恢复可执行IR仍为0，没有使用标签或改变thinking选择；见`rr_v2_evidence/strict_contract_round2/all_original_outputs_recovery.json`。

## 已实施的严格契约与闸门

严格响应schema约束expression/connector/unsupported分支、8类绑定值、7类连接器、固定operator参数个数、精确接口键及当前公开原文的source单元范围。保留unsupported；原后端继续负责变量、运算类型、来源节点和执行检查，不将JSON形状当成语义正确。

同一原账本追加第二轮授权和状态，不改任何原调用行。最多新增12个物理生成请求，固定同20 TRAIN来源中OE/Airline/SARA各4个，按原预定次序；原提示原文、ON、seed45及全部采样参数不变，只换响应schema。原serving tokenization与当前本地tokenizer逐token核对一致后复用，未新增tokenize POST。首阶段至多2次，任一闸门失败立即停止；两个通过后仍先审阅实际证据，才能继续剩余项。

相关离线检查 **125 passed**，测试进程禁止网络；Ruff检查通过。新增检查包括无歧义恢复不补造语义、schema拒绝缺失分支与假source、对执行结果而非模型另给答案评分、source字面值核验、失败扣额后停止、两次闸门成功才允许后续，以及总量96封顶。离线日志及源文件hash：`rr_v2_evidence/offline_latest.{json,txt}`。

12个source-bound schema各通过26个实际token解码用例，共312个人工语法用例；本地仅加载固定tokenizer，未加载模型权重，网络被禁止。预检查不是模型效果证据。记录：`rr_v2_evidence/strict_contract_round2/backend_schema_precheck.json`。

## 首个真实请求及停止原因

来源：`OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028`。它是原固定顺序中的首个受影响来源，没有按新结果选题。

| 验证层 | 真实结果 |
|---|---|
| API请求 | 完成，finish_reason=stop，无网络重试 |
| 严格JSON响应schema | 通过 |
| IR运算类型 | 未通过：`Nonboolean operand` |
| 程序完整执行 | 未完成 |
| 程序结果与TRAIN参考答案比较 | 未进入；没有用模型另给的答案冒充程序结果 |
| 闸门决定 | 失败，停止，未发第二次请求 |

模型将EC/EV答案及旧程序序列化进scalar字符串，然后给出`{"op":"and","args":["s157"]}`。`s157`是来源编号字符串，不是布尔命题；source_links还把它当作语义节点。公开来源核验也无法支持这些字符串绑定。将它强转为true、将字符串答案拆出来直接返回、或补上新的查询，都会替换缺失的语义，因此没有采用。对新原文再做既定无损适配为0处，错误保持原样。

完整原始request/wire/result和validation在`artifacts/rr_v2_preflight/strict_contract_round2/`；精简失败分析在`rr_v2_evidence/strict_contract_round2/failure_analysis.json`。运行进程session62285已退出0，账本状态为stopped，inflight为空。复制实际账本验证下一请求会被拒；禁止generation方法后恢复同一终态，模型及oracle增量均0。

## 成功与未解决来源

- 本轮新增、通过类型/执行/对应语义检查的修复成功来源：**0**。
- 已实测但未解决：上述首个OE来源，共 **1**。
- 原计划其余受影响来源：**11**，按停止规则未调用；没有将未调用项记为通过。
- 原固定20来源中的另外8个未成为本轮目标：4个PW仍由独立公开Horn后端执行，4个ContractNLI保留原生NLI/fallback范围。这些既有结果不算本轮模型IR修复成功。

20个来源的逐项状态、成功空清单、失败来源及11个未调用来源的完整ID，见`rr_v2_evidence/strict_contract_round2/source_outcomes.json`。

## 实际请求、token、时间及费用

| 范围 | executor请求 | prompt token | completion token | 合计token | 已记录调用耗时/秒 |
|---|---:|---:|---:|---:|---:|
| 第二轮新增 | 1 | 15566 | 1986 | 17552 | 64.614 |
| 全部累计 | 85 | 510536 | 227197 | 737733 | 6608.670 |

本轮API请求完成但IR验证失败，仍完整计额。无重试、无新增teacher或oracle请求。teacher累计2次（1成功、1失败），已知输入21564、输出372，失败usage未知；这些不被删除或填成0。

执行器沿用既有本地服务，逐请求增量API现金0；GPU货币成本未知，不能将token换算成未经提供的美元费用。teacher本轮增量0，既有teacher没有逐请求现金发票。机器运行资源和模型服务未重启。

实际汇总、费用口径、首轮86行及原metadata完全保留的hash证明：`rr_v2_evidence/strict_contract_round2/round2_summary.json`。第二轮授权剩余11次保留，不因全局还有15次空间而继续调用。

## 原固定预检与实现交付

原40个thinking对照及唯一8个OE修复保留。有效20对ON为5/20结构、9/20来源全部任务正确、153438 token、1776.832秒；OFF为8/20、10/20、132899 token、1215.601秒。ON19条非空reasoning、OFF0条，且1个SARA来源ON正确/OFF错误，因此按固定零harm规则保留ON。没有新增profile/seed扫描；证据`thinking_completion.json`。

原同20来源小试36次调用完整完成，50个额外事实视图含1个失败，全部占额；生成4条参数化模式、首16来源teacher、首批快照与冻结部分库。原禁止网络/新子进程的实际恢复增加模型0次、oracle0次，见`actual_pilot_restore_verified.json`。这36条模型提议没有可执行IR，4个稳定结果来自PW公开语法；第二轮另1条也未通过，不能写成已恢复跨库规则编译。

| 模块 | 已交付内容 | 现有证据与范围 |
|---|---|---|
| A | `coverage.py engine.py public_horn.py routing.py` | 源登记、非空Ω、TOP/域外/冲突/超时、有限域双世界与联合批次、共享上下文成本、撤销与实际路由；未知自然语言残余不删除 |
| B | `interfaces.py learning.py source_learning.py` | 8字段、7连接器、实体/分组/额度/次序、≤4计费视图、参数化合并与冻结；真实20来源库保留 |
| 普通连接对照 | `example_synthesis.py formal.py` | 同提议/同监督，PW16个已有视图参与普通连接筛选，H不等于Ω |
| 适配、分区、评分 | `adapters.py partitions.py data_store.py scoring.py` | 128/40/160来源整组划分，固定20 TRAIN白名单，原生评分及失败分母；未用测试标签调试 |
| 预算及恢复 | `ledger.py client.py checkpoint.py schema_validation.py` | 原6000/20总账、当前100/2、第二轮≤12且本轮总≤96、失败保留、两请求闸门、停止后禁止续发与恢复不重复计费 |
| 后续入口 | `controls.py routing.py formal.py` | 六臂相同工具/最多3调用、共享材料、B1/B8/原生空库/诊断代码；本次不执行 |

125项离线与312个语法用例证明对应的实现行为；实际闸门反例表明它们没有证明模型能产生语义有效程序。原始5个AST锁定失败没有修改。

## 绑定、保存和最终结论

- 本轮实现提交：`ecd0ea8`；科学代码hash `ef4dd1e10bac8190ad4ad5a35aed728940c3442612bbf4e9d899d5c153ef1d58`。
- 模型/方法配置hash：`ce3f15a5e0544b1dab5c84bfb7a4a122c7f072bf42a9efa60c4f8f4f4b3946a3`。轮次操作授权另行记录，没有调采样参数。
- 数据hash：`5b7683f05c921598c4bab6dc29834df3dc7595e3795d46551732446efa3eacc0`；来源清单hash：`ef0f419d13f5219f0faeb97543b52d27be8c50a67243103e542013dc24ae3ca4`。
- 本轮seal：`artifacts/rr_v2_preflight/strict_contract_round2/seal.json`，12请求payload哈希在同目录；旧源码/运行时/账本封存于`preserved_before_strict_schema_round2/`。第一轮所有86行及metadata逐项不变，oracle仍50行。
- 原研究v0.23、utility v6、原数据、失败及模型服务保留；仅原根两份获授权状态文档同步。所有旧科学绑定按原阶段保存，不把旧结果改标为新代码实测。
- 当前`formal_readiness.json`为此前正式入口补线的历史组件兼容性证明，不能用于当前主训练启动。最终结论：`training_readiness_decision.json:formal_training_ready=false`。

**本次遵照失败停止规则，保留11次额度；没有第二次或后续调用。原goal条件仍未全部满足，不标完成。** 完整复现、原始证据和来源清单已交付；不会从这一个失败样本或人工检查推断整体已经通过。
