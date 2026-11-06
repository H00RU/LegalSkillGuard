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
