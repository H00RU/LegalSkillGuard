# LegalSkillGuard RR-v2 当前检查报告

本阶段实现与原固定20来源工程预检已完成，当前版本恢复及正式路径准备凭据已核验。主训练、六臂正式评测、冻结测试和论文均未启动。同一Goal已由工具确认完成，仅关闭本阶段限定目标；不表示未覆盖能力或全部法条语义已经验证。实现提交`ba1eded37986fa67be74d4578ce26ed129ebd700`。

本结论依据原交接的工程验收条件（第42、54、56行）和方案第三步：语义未解决项须保留状态，不要求20/20正确或显著涨分。最新补充要求A、B各有真实主路径和对应语义证据，已单列，回退不计入核心成功。下面单独报告所有语义失败；“工程预检完整”不表示法律推理或法条翻译全部通过。

## A、B核心验收与fallback

按最新验收补充，fallback答对、旧结果重放和默认输出均不计核心成功。另在原固定4个ProofWriter来源上各进行1次新的真实executor请求，调用共用ingest_source，B直接执行learn_source，未返回缓存学习结果；缓存只提供原已扣账oracle的期望标签。

| 方法 | 新真实主路径语义通过 | 固定20来源覆盖 | 非核心/回退比例及原因 |
|---|---:|---:|---|
| A | 4/4新验证来源 | 4/20（20%） | 16/20（80%）：12个自然语言规则来源未获完整语义/稳定证书，4个ContractNLI按设计native fallback；其中native回退答对6条，不计核心成功 |
| B | 4/4新验证来源 | 4/20（20%） | 16/20（80%）未获已核验可执行连接：8个金融/费用来源仅membership字段，4个SARA为字段提议/无碰撞/参考失败，4个ContractNLI无反事实oracle；这些均不计核心成功 |

A真实证据来自当前受限公开文法编译、completion_theory及Ω稳定性检查，输出为Unknown/False而非固定默认标签；本次真实样本覆盖全编译后稳定分支，残余TOP、相关未译例外、无关残余和联合补译等分支有离线反例验证，本次不宣称这些分支已真实命中。B分别观察6、4、6、6个真实粗粒度碰撞，细化entity_equality后观察映射无冲突，执行连接在原来源及4个参考视图上共20次语义检查全匹配；真实覆盖仅为实体见证连接，分组cap和共享额度等未被冒充为真实主路径成功。

最初核验脚本附加了“候选H必须减少”的条件，已撤销这一非原方案门槛。原始检查与全部候选数保持不变；当前以碰撞被字段区分及实际连接执行语义核验。保留H歧义，不宣称H等于Ω或唯一识别。详见[独立A/B证据](rr_v2_evidence/semantic_preflight/core_acceptance.json)及[新真实路径逐字恢复](rr_v2_evidence/semantic_preflight/core_wire_compatibility.json)。

## 实际结果

- 20/20当前记录齐全：12个受影响来源经共用两次联合调用重新验证，8个未受影响来源免费重放，来源、seed、模型与采样不变。新增executor28次（契约修复24、核心主路径4）、teacher1次，无应用层自动重试。
- 新24条中schema有效21条、模型IR实际执行19条、IR输出匹配原TRAIN答案3条；完整严格修复检查通过0条、涉及0来源。未通过项均保留。
- 最终native任务答案匹配10/20来源，未解决10/20。稳定来源4条，稳定但错误0条；未解决NL任务均未获得稳定性证书。最终native答案、IR候选结果和严格语义检查分列，未按训练答案选择二者。
- 144项相关离线检查通过；12来源72个实际token类型用例和1个真实第二次输入复用用例通过。当前20来源B学习在禁网络、禁子进程、禁新增oracle条件下复算，全部与原结果一致。
- 首批16来源完成实际教师汇总，最后4来源按原方案保留待接续的部分批次。20来源checkpoint、部分库和六臂共享材料已保存；禁网络和子进程重复恢复不新增模型调用或oracle。
- 修复后的评分器免费重算原40条thinking比较：ON9/20、OFF10/20，ON正确而OFF错误来源仍存在，按原固定判据继续ON。没有新增对照调用。

## 问题分类与修改

已修复的实现缺陷是：跨适配器提示示例外溢；预检仍发送旧source-free schema；共用训练和推理的第二次调用没有传递一致的source/previous schema；OE评分缺原生类型校验、把数组顺序及1/1.0当作语义差异。现在统一schema传递，已有公开字面值可按原值复用，原生EC/EV映射采用保留重复项的无序完整比较，金额精确比较，官方F1不变。

原工程预检36条共用请求及另外4条新核心主路径请求已全部免费重建：24条新请求的wire字节精确一致；12条沿用请求仅规范化三项结构化元数据内部的JSON键顺序，公开文本、值、schema和其他字段不变。全部输出重放一致。跨适配器修复后重新完成20来源零调用恢复，生成绑定保留`077a748c30fd1acf3dd447c1e54bab826374bc1fd74e0709503c3e09006dd14a`，当前执行绑定另列，历史记录未覆盖。

删除按`s_asset`变量名推断资产已提取完整的额外假设；执行器仍拒绝重复输出键。旧95号错误没有被合并为新答案。旧36条输出经47次可逆格式修正仍缺规则/query/分支或已截断，不能恢复可执行IR；旧85–96号响应现行代码免费重放后严格检查仍0通过。

剩余模型错误包括：错解法律查询、错用费用或豁免规则、错引用源段、把节号自身相等当作规则条件，以及在固定token上限内未完成JSON。SARA有IR标签正确而native fallback错误的实例，也有恒真空壳程序标签碰巧正确的实例；未借助参考答案补造规则或改选答案。公共字面值检查不证明普遍自然语言等价，原方案的翻译忠实性条件保持明确。

先前验收解释把“严格修复闸门0通过、9来源未在修复后重验”泛化为整体小试未完成。原20来源小试当时已执行；真正工程缺口是现行共用路径及当前版本恢复/准备凭据。本次补齐这些缺口，同时保留严格语义失败，未追加100%准确率门槛。

## 原验收逐项核验

| 条件 | 当前证据 |
|---|---|
| A覆盖/TOP/冲突/域外/超时、H与Ω分离；B join/cap/共享额度/次序/见证 | 144项网络阻断离线检查；原方法和实现映射保留 |
| 五库适配、数据划分与隔离 | 固定数据manifest、TRAIN访问白名单、分区测试；无新来源/测试标签 |
| thinking真实开关与一次固定选择 | 原真实记录及本次40条免费重评分，继续ON |
| 20来源真实流程、解析/执行/接口、失败处理 | 当前20来源完整记录；24条新真实请求；B20来源缓存复算完全一致 |
| 首16来源教师汇总、剩4来源待接续 | 当前实际teacher_batch1及partial batch状态 |
| 部分库、checkpoint、同账恢复 | 当前20来源免费恢复；98旧请求/77旧meta/50oracle逐项不变 |
| 六臂共享材料及正式路径接续 | 当前科学绑定的formal_readiness_core.json已validate，未启动正式运行 |
| 调用、token、费用、时间、旧记录保留 | request_ledger.csv/json、summary.json、final_metrics.json及原SQLite |
| 原范围、预算及关闭开关 | 原6000/20及原桶；固定20来源；全部正式开关仍false |

## 来源级结果

“native正确”只指完整任务答案匹配；“严格通过”另外包含IR执行与公共溯源检查。完整ID、每次检查和工件位置见[source_status.json](rr_v2_evidence/semantic_preflight/source_status.json)。

| 原index | 数据集/ID前缀 | 方式 | native正确 | 可执行IR数 | 严格通过数 | 状态 |
|---:|---|---|---|---:|---:|---|
| 0 | OpenExempt:4f3b7eff8dad | 真实重验 | 否 | 2 | 0 | translation_unresolved |
| 1 | RuleArena_Airline:e88c2c8f441b | 真实重验 | 否 | 1 | 0 | translation_unresolved |
| 2 | SARA_v2_Binary:815f377b6412 | 真实重验 | 否 | 1 | 0 | translation_unresolved |
| 3 | ProofWriter_OWA_depth5:43ec41194db9 | 免费重放 | 是 | 0 | — | completion_stable |
| 4 | ContractNLI:d9360f2a8c03 | 免费重放 | 是 | 0 | — | translation_unresolved |
| 5 | OpenExempt:fe5acb6c9806 | 真实重验 | 否 | 2 | 0 | unsupported_no_certificate |
| 6 | RuleArena_Airline:9b47bd06b2ac | 真实重验 | 否 | 2 | 0 | translation_unresolved |
| 7 | SARA_v2_Binary:8175fcb9abeb | 真实重验 | 是 | 2 | 0 | translation_unresolved |
| 8 | ProofWriter_OWA_depth5:e95366c59474 | 免费重放 | 是 | 0 | — | completion_stable |
| 9 | ContractNLI:e671a984356f | 免费重放 | 是 | 0 | — | translation_unresolved |
| 10 | OpenExempt:ae1e4bdb9abb | 真实重验 | 否 | 1 | 0 | translation_unresolved |
| 11 | RuleArena_Airline:92d91f15d181 | 真实重验 | 否 | 2 | 0 | translation_unresolved |
| 12 | SARA_v2_Binary:5c29a3a22f75 | 真实重验 | 否 | 2 | 0 | translation_unresolved |
| 13 | ProofWriter_OWA_depth5:d7b97c798724 | 免费重放 | 是 | 0 | — | completion_stable |
| 14 | ContractNLI:354623271a54 | 免费重放 | 是 | 0 | — | translation_unresolved |
| 15 | OpenExempt:cdf5d6eb5caa | 真实重验 | 否 | 0 | 0 | translation_unresolved |
| 16 | RuleArena_Airline:575fd48cab69 | 真实重验 | 否 | 2 | 0 | translation_unresolved |
| 17 | SARA_v2_Binary:097568705cac | 真实重验 | 是 | 2 | 0 | translation_unresolved |
| 18 | ProofWriter_OWA_depth5:f39b4cd5a6fa | 免费重放 | 是 | 0 | — | completion_stable |
| 19 | ContractNLI:442c36c12745 | 免费重放 | 是 | 0 | — | unsupported_no_certificate |

## 请求、实际费用和时间

累计executor **124/6000**、teacher **3/20**。原thinking40、建库36、恢复48；恢复桶原上限232不变。失败、截断、重试均计数，待结算0；没有清账或重置历史限额。旧96/100与teacher2仅是已被最新用户授权取消的预检子上限。

本次executor输入/输出token：`{'prompt_tokens': 189505, 'total_tokens': 295672, 'completion_tokens': 106167}`，累计请求时延3232.461秒；本次teacher可观察usage：`{'input_tokens': 21524, 'cached_input_tokens': 0, 'output_tokens': 418, 'reasoning_output_tokens': 121}`，时延22.403秒。executor全历史token：`{'prompt_tokens': 806463, 'total_tokens': 1177858, 'completion_tokens': 371395}`，时延11049.617秒；teacher全历史已知usage：`{'input_tokens': 43088, 'cached_input_tokens': 0, 'output_tokens': 790, 'reasoning_output_tokens': 192}`。reasoning token是输出的子集，不重复相加。

本地executor新增按次API现金费用为US$0（既有服务，无按次API账单），GPU成本没有可用计价账单，不能记作零总计算成本。teacher通过既有授权CLI运行，现金账单不可得；旧失败teacher调用usage/费用未知，次数已扣除。未新增付费资源，也未使用未授权模型。

## 可复现与证据

科学绑定`47cddfaed75c295bf7655a7a2167e940db85c7c2b7520625a9534e746baa6b14`；配置语义绑定`ce3f15a5e0544b1dab5c84bfb7a4a122c7f072bf42a9efa60c4f8f4f4b3946a3`；数据绑定`5b7683f05c921598c4bab6dc29834df3dc7595e3795d46551732446efa3eacc0`；manifest绑定`ef0f419d13f5219f0faeb97543b52d27be8c50a67243103e542013dc24ae3ca4`。

工作目录`/home/yndx/hhy/legal-skill-rr-v2`，分支`research/legalskillguard-rr-v2`。离线复现：`/home/yndx/hhy/legal-skill-current/.venv/bin/python -m experiments.rr_v2_offline`。当前已完成记录的`python -m experiments.rr_v2_semantic_preflight finish`可再次免费恢复；先核实账本和进程，不能重复启动未结算请求。

[诊断及字段证据](rr_v2_evidence/semantic_preflight/diagnosis.md) · [逐请求账本](rr_v2_evidence/semantic_preflight/request_ledger.csv) · [费用与计数](rr_v2_evidence/semantic_preflight/summary.json) · [完整指标及成功/未解决ID](rr_v2_evidence/semantic_preflight/final_metrics.json) · [B复算](rr_v2_evidence/semantic_preflight/learning_replay.json) · [免费恢复](rr_v2_evidence/semantic_preflight/restore_after_core.json) · [当前准备凭据](rr_v2_evidence/formal_readiness_core.json) · [授权](../docs/rr_v2/original_budget_preflight_authorization.json)。

## 阶段结论与最小下一步

本次没有调整研究问题、A/B机制、数据或模型方案；已完成当前范围的工程修复和完整固定来源预检，另补齐A、B各自新真实主路径语义证据。模型法条翻译与任务语义仍存在上表所列未解决项，未宣称法律推理质量已验证。核心覆盖和fallback比例已明确；未把这些任务回退计为A或B核心验证成功。原方案允许将这些状态保留进入后续固定研究流程；它们不被当作已核验编译结果或稳定证书。

无需新增预检额度。本阶段停止；最小下一步是审阅未解决来源和本报告，再另行决定是否授权原定128来源主训练。本次保持全部正式开关关闭，不自动进入训练、评测或论文。

<!-- HISTORICAL_REPORT -->

以下为最新授权前历史报告；其旧额度、blocked及尚未重验数量均已由上述当前状态取代。

---

# LegalSkillGuard RR-v2 当前检查报告

完整goal未完成，正式训练尚未就绪。三轮复核同一额度/语义阻断后，Goals工具已标记blocked；本次复核没有新增调用。当前结果仅属于原固定20个TRAIN来源的修复预检；未启动主训练、正式评测、冻结测试或论文。

账本executor **96/96**（全局100硬上限），teacher **2/2**；新增11次，剩余0次，待结算0次。失败和重试均计数，客户端及底层自动重试为0。旧87行（85 executor+2 teacher）、旧meta和50条oracle记录核验不变。

用户已取消旧修复轮数和首错停止限制。失败来源重试须有具体修改及离线证据；修复验证通过后，同版本可继续未完成固定来源，不新增来源、种子或测试标签。授权及工程边界见docs/rr_v2/cumulative_repair_authorization.json。

## 契约修复证据

原36条输出经47处可逆格式适配仍为0条可执行IR：缺query、缺分支、截断或明确unsupported；未补造语义。第85条暴露布尔操作数及source node契约不一致；第86条暴露金额作对象键，第87条暴露无界嵌套和截断。原文、真实失败回归、前后契约与修改依据均保留。

实现提交：d3a3803（类型/节点及账本），28eceb4（16层AST），7a01fce（原任务），2aafb3d（字面量），29d37f3（闭合输入），9d11dcc（原生字段类型），ca06ff3（解码正则引号边界），a00ce55（资产键唯一性）。当前137项网络阻断离线检查、12来源共86个实际token解码用例通过。第94条实际非法JSON在旧xgrammar语法中被接受为前缀，新语法明确拒绝。闭合输入修复仅在已有四个输入均通过逐字溯源的原OE来源上真实验证，未推广成全训练已就绪的结论。采样、thinking ON、模型与seed45保持原定设置。

证据：`reports/rr_v2_evidence/cumulative_repair/contract_audit.json`、`revision_v2_audit.json`、`backend_precheck.json`；实际请求及验证：`artifacts/rr_v2_preflight/cumulative_repair/`。每次请求保留request/wire/result与validation；自第二版起另存字节级wire_request。

## 本次物理请求

| 累计序号 | 来源 | 版本 | 结果 | token | 秒 |
|---|---|---|---|---:|---:|
| 86 | OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028 | typed_contract_v1 | no_executable_model_IR | 15732 | 55.698 |
| 87 | RuleArena_Airline:e88c2c8f441b03bf1e690f5c49450dc95e2fa39d19e589745164f6786caf47a8 | typed_contract_v1 | strict_schema_or_JSON_failure | 14458 | 239.455 |
| 88 | RuleArena_Airline:e88c2c8f441b03bf1e690f5c49450dc95e2fa39d19e589745164f6786caf47a8 | typed_contract_v2 | TRAIN_semantics_or_source_grounding_unresolved | 12468 | 194.194 |
| 89 | SARA_v2_Binary:815f377b6412d8c0e4b3cd0095e029728c40bc80387b97d7a0234efc72d11dac | typed_contract_v2 | TRAIN_semantics_or_source_grounding_unresolved | 3823 | 26.014 |
| 90 | SARA_v2_Binary:815f377b6412d8c0e4b3cd0095e029728c40bc80387b97d7a0234efc72d11dac | typed_contract_v3 | TRAIN_semantics_or_source_grounding_unresolved | 3887 | 23.480 |
| 91 | SARA_v2_Binary:815f377b6412d8c0e4b3cd0095e029728c40bc80387b97d7a0234efc72d11dac | typed_contract_v4 | TRAIN_semantics_or_source_grounding_unresolved | 4644 | 43.817 |
| 92 | OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028 | typed_contract_v4 | no_executable_model_IR | 15732 | 63.136 |
| 93 | OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028 | typed_contract_v5 | TRAIN_semantics_or_source_grounding_unresolved | 16271 | 72.669 |
| 94 | OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028 | typed_contract_v6 | strict_schema_or_JSON_failure | 22396 | 265.189 |
| 95 | OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028 | typed_contract_v7 | no_executable_model_IR | 17532 | 111.325 |
| 96 | OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028 | typed_contract_v8 | TRAIN_semantics_or_source_grounding_unresolved | 17510 | 113.510 |

通过只指：严格schema、类型、实际程序执行、公开来源溯源、该程序输出的原固定TRAIN语义检查全部成立。单独模型答案、fallback正确或JSON可解析均不算修复成功。

## 原固定20来源状态

| 序号 | 来源 | 当前状态 | 新请求序号 |
|---|---|---|---|
| 0 | OpenExempt:4f3b7eff8dad708e09a3be5b3fbbf47518636ae0edc8e9acf286586350c7e028 | 已验证，仍未解决 | 86,92,93,94,95,96 |
| 1 | RuleArena_Airline:e88c2c8f441b03bf1e690f5c49450dc95e2fa39d19e589745164f6786caf47a8 | 已验证，仍未解决 | 87,88 |
| 2 | SARA_v2_Binary:815f377b6412d8c0e4b3cd0095e029728c40bc80387b97d7a0234efc72d11dac | 已验证，仍未解决 | 89,90,91 |
| 3 | ProofWriter_OWA_depth5:43ec41194db931b0e509a68dddf476b80e9edb3c5b98cdc6ce889b19314ba096 | 公开Horn后端已验证 |  |
| 4 | ContractNLI:d9360f2a8c03efc35524289167a83e9505ebae476367505b868af29f37fcffa0 | 原生fallback已有记录，无形式认证 |  |
| 5 | OpenExempt:fe5acb6c980638b2750321e28fadcc69d98f49992871bfc44accbc3b147ca597 | 额度内未验证 |  |
| 6 | RuleArena_Airline:9b47bd06b2ac8dec3e43933c48c3879746f949879683fa2977b397b1253a0f74 | 额度内未验证 |  |
| 7 | SARA_v2_Binary:8175fcb9abeb3ba15e5b58a33f9b479944ee37eab0c0cfa9557393b5193ece97 | 额度内未验证 |  |
| 8 | ProofWriter_OWA_depth5:e95366c5947484c083f10b4fea4f936a17ec6bb58ed903aa3f1d376b7105c2dc | 公开Horn后端已验证 |  |
| 9 | ContractNLI:e671a984356facb0c0666809e219fa44fa18d30e4f6252bbb33d8869fc43b1c9 | 原生fallback已有记录，无形式认证 |  |
| 10 | OpenExempt:ae1e4bdb9abb4f7bea56b7d39a89776db8e4ed5f2ee7048f51e882a3555c9244 | 额度内未验证 |  |
| 11 | RuleArena_Airline:92d91f15d181b5cdd9aedcaaa188e357186216ad80ed0937918e585c673f5fc3 | 额度内未验证 |  |
| 12 | SARA_v2_Binary:5c29a3a22f755d6a6253919de3327553f029a75827c72238547ebb6701b5ace7 | 额度内未验证 |  |
| 13 | ProofWriter_OWA_depth5:d7b97c7987247373053b23e1864494f8ae060e88d4ffe4d3bd6feccff9906d6b | 公开Horn后端已验证 |  |
| 14 | ContractNLI:354623271a5433b9d6fe42ec70538acd25e9f7e37aee568c81e2e7d4912f9450 | 原生fallback已有记录，无形式认证 |  |
| 15 | OpenExempt:cdf5d6eb5caa700c844bb8f89116b4ba97d73b5011e69e2919c02c00aeb63ef7 | 额度内未验证 |  |
| 16 | RuleArena_Airline:575fd48cab69790e778702dd8893fb94deed82d16569037977193dd30f6d32b3 | 额度内未验证 |  |
| 17 | SARA_v2_Binary:097568705cac232354a1b0bc169fad14d5b105d2818fdebc5622f304975c747e | 额度内未验证 |  |
| 18 | ProofWriter_OWA_depth5:f39b4cd5a6faf7e199c568e2487db5b6b0e27fadefef4f319d42655e4fe04d94 | 公开Horn后端已验证 |  |
| 19 | ContractNLI:442c36c12745965b79f777dedc7bc3dc249d80ca444c395ece6ec7953c15c07f | 原生fallback已有记录，无形式认证 |  |

## 实际费用及验收

本次新增executor token：106422输入 + 38031输出；请求耗时合计1208.486秒。全部executor token：616958输入 + 265228输出。

本地executor新增API现金支出$0；GPU货币成本未定价，不能称总计算免费。teacher未新增；原两次中的成功调用已知21564输入、372输出token，另一次失败usage及实际账单金额不可得。逐次费用和未知量见requests.json。

最终结果：11次新增物理请求用完，6次返回可执行模型IR，但完整闸门成功来源为0；3个受影响来源已验证仍未解决，9个未进入修复后正常来源预检阶段。第96条通过schema、类型、执行和原生字段格式，EC/EV完整匹配均false，查询引用未由其已链接规则行支持，故不改判通过。4个原PW来源仅有独立公开Horn后端证据，4个CNLI来源仅有原生fallback记录，均不能算本轮模型IR修复成功。

无网络实际恢复命中11条新请求缓存，当前v8完整验证结果按持久化JSON值精确重算一致；没有调用、账本行或oracle增加。原账本87行、旧meta及50条oracle不变。账本完整副本上的额外请求被Cumulative96拒绝。证据：actual_restore_verified.json、hard_cap_verified.json。

完整goal仍未达到：受影响来源整体语义预检未通过，当前20来源完整训练链条没有通过当前版本验收；正式入口兼容凭据仍属旧9eb阶段，不能作为当前4ccc版本就绪证明。闭合输入只在当前定点修复支路验证，未声称通用训练二次解析均已接入或有效。完整原需求逐项状态见docs/rr_v2/requirements_status.json。

精确复现：使用保存的对应revision源码及seal；当前入口`python -m experiments.rr_v2_cumulative_repair`，不重启旧thinking/pilot。离线：`python -m experiments.rr_v2_offline`。原始数据/配置与版本绑定见各revision/seal.json。

## 当前封存绑定与复现证据

- code_hash: `4ccc8f79e9a367de41cbea11ae52189d0fc72e7f28a6e99124206ceab2ec1dac`
- config_hash: `ce3f15a5e0544b1dab5c84bfb7a4a122c7f072bf42a9efa60c4f8f4f4b3946a3`
- data_hash: `5b7683f05c921598c4bab6dc29834df3dc7595e3795d46551732446efa3eacc0`
- source_manifest_hash: `ef0f419d13f5219f0faeb97543b52d27be8c50a67243103e542013dc24ae3ca4`
- preflight配置文件字节SHA256: `7d104e29bfaa8cc32dd5f4d7ac007d20ab9285db6dca557de5a69107f19be010`
- protocol文件字节SHA256: `3e0d5f7818ad50251dd4e0bab4ad722e420c55d79ef70b7ac853a6552d322947`

当前完整响应还在服务实际`any_whitespace=false`选项下重放接受并正确终止，见`rr_v2_evidence/cumulative_repair/actual96_serving_decoder_replay.json`。源码、完整保护清单、137项离线收据和实际费用最终核对见`final_integrity_verified.json`；新旧请求与全部原始失败均保留。复现命令见[REPRODUCE.md](../docs/rr_v2/REPRODUCE.md)。
