# 组合编译基线：已运行，新增跨合同覆盖为0

固定原TRAIN的7份获取合同和2份既有诊断合同上，接入NQG官方组件后，61个真实原文—语义配对归纳为62条语法规则，其中17条带组合变量。61个配对全部可回放；7份获取合同仍为12个新主路径判断且均符合原生答案，2份诊断合同仍为0/4目标主路径。逐来源结果与原10条完整模板基线相同。**通用组合语法已经实现，但当前获取资产没有带来跨合同覆盖增量；不能据此成立第一项贡献。**

本次新增模型请求0，累计9287E/172T、在途0；没有完整训练、DEV或TEST。实际输出和未成功结果全部保留。

## 实际接入与比较

复用上一轮真实自由强对照学出的编译器、10个无歧义源注释、词典和原程序。方法侧独立教师获取的超时仍完整保留；本次属于共享资产上的算法比较，不补记为独立方法获取。

- [当前实现](../../legal_skill_guard/skill_evolution/compositional_compiler.py)、[固定运行入口](../../experiments/legal_skill_evolution_compositional_compiler.py)、[回归](../../tests/test_skill_evolution_compositional_compiler.py)。
- [NQG原论文](https://aclanthology.org/2021.acl-long.75/)与[官方归纳代码](https://github.com/google-research/language/blob/865fae65f63ef7e6b2989d4ff8b47f61750415a8/language/compgen/nqg/model/induction/induction_utils.py)。依赖闭包12个源文件，固定提交865fae65，Apache-2.0；[逐文件来源及哈希](../../legal_skill_guard/_vendor/nqg/UPSTREAM.json)。仅搬迁包导入路径，不引入TensorFlow、预训练模型或额外数据。
- [固定协议](compositional_compiler_evidence/indexed_enumeration/protocol.json)、[实际获取配对](compositional_compiler_evidence/indexed_enumeration/acquired_examples.json)、[冻结语法](compositional_compiler_evidence/indexed_enumeration/frozen_grammar.json)、[逐来源结果](compositional_compiler_evidence/indexed_enumeration/completed.json)。

配对由已获取的完整记录、对齐槽和词典别名产生。语义原子使用可逆编码，源中的NT_1、括号或中文不会改变语法结构。raw值必须能无歧义回绑实际源子串，类型和常量必须符合已获取记录构造；角色需要在实际记录区间有已学别名见证。部分识别的角色集保留partial标记，不变成完整集合或未知即否定。归纳不读原生答案；冻结语法后再打开原TRAIN评分。两份诊断合同已有前次结果，明确不是新盲测。

参数采用官方GeoQuery的编码代价8/1，固定无重复目标非终结符，全配对/全相关编码成本计算，不扫描参数。程序保持原教师输出。图表中的主路径正确指native标签正确，尚不能推导全部法律条件的语义均已形式证明。

## 真实运行与工程修复

原官方SPLIT实现先物化源/目标区间的笛卡尔积，再检查是否至少一侧规则已经可推导。本次在第一条长条款上62.7秒仍未完成，观察到内存约2.6GB，已停止并保留[原协议和日志](compositional_compiler_evidence/upstream_enumeration/induction.log)、[停止原因](compositional_compiler_evidence/upstream_enumeration/stop_summary.json)。

[索引实现](../../legal_skill_guard/skill_evolution/nqg_indexed_splits.py)按已有可推导规则的规范化源序列检索：已知内规则时直接确定目标子串；已知外规则时由目标前后缀确定唯一的新孔。两类恰好覆盖官方NEW的成员资格条件，之后仍调用官方规范化和候选校验。对含0/1/2阶变量、目标换序和重复片段的小例，逐项候选集合与原枚举相同；未改变MDL目标或接纳条件。该优化服务当前接口，不计论文创新。

索引版实际归纳5.699秒，进程总耗时6.073秒；9份完整合同解析和程序执行总计33.417秒。保留[完整归纳日志](compositional_compiler_evidence/indexed_enumeration/induction.log)及[可读17条组合规则](compositional_compiler_evidence/indexed_enumeration/readable_compositional_rules.json)。原官方枚举尚未完成，不能据此给出准确的完整加速倍数。

## 原生执行结果

每母合同仍有4个原生视图；当前编译器只处理nda-5/7，其他视图保留真实历史fallback，母来源分母不变。

|原TRAIN母合同前缀|原模板主路径正确/执行|NQG主路径正确/执行|原模板与NQG母来源grade|
|---|---:|---:|---:|
|8af247c6|2/2|2/2|1.00|
|d50f9bcd|2/2|2/2|.75|
|35462327|0/0|0/0|.75|
|62fda7e9|2/2|2/2|.75|
|d9360f2a|2/2|2/2|.75|
|e671a984|2/2|2/2|.75|
|442c36c1|2/2|2/2|1.00|
|4d4e550a，既有诊断|0/0|0/0|1.00|
|de427b59，既有诊断|0/0|0/0|.75|

9母合同36视图：12个编译主路径、12个native正确，24个fallback，占66.7%。获取合同内的12个正确判断可以复现，诊断合同的得分完全来自历史fallback，不能计为机制成功。两个版本答案、grade和覆盖均无新增增量。

## 失败定位及研究决定

[覆盖失败证据](compositional_compiler_evidence/indexed_enumeration/coverage_failure_certificate.json)逐一检查10个输出法律记录的语法构造头。**两份诊断合同中，每个构造头都至少有一个必需终结词不在该合同中出现。**因此当前语法不可能产出对应法律记录，任何改变解析顺序或重复请求均不能补齐。具体如Cyber/Participating Entity、whether、Paragraph等词仍固化在构造头中。即使词均出现，也还需满足顺序和结构；这个必要条件已经足够排除本次两合同的覆盖。

这将当前缺口定位到**获取的可迁移语义及构造头抽象**：角色列表和槽已经能组合，句式/实体称呼仍绑定少量原文。NQG不会自行获得未知法律表述的同义关系；继续在这些原注释上压缩不能补造这种知识。原语义程序对限定项的解释也未因引入语法而自动改进。

决定：冻结完整模板和本NQG版本为共同强基线，不扩大同路径批量实验。下一项实际研究仍围绕源获取：在同一原TRAIN信息及固定原文上，让获取者明确给出可迁移构造与实例对齐、角色称呼和限定项的源见证，比较结构化获取与独立自由程序获取的可靠性和全部成本。获取协议须在真实比较前说明具体更新操作及其额外能力，通用文法、确定性源绑定或多一层格式本身不计贡献。未证明增量前不扩展完整研究，也不更换五库为其寻找正例。

## 数据适配与账本

[论文模块证据及128来源/280视图审查](METHOD_EVIDENCE_AND_TRAIN_FIT.md)保留其结论：数据血缘和母来源隔离通过；任务各自能检验的能力不同。ContractNLI提供异合同条款及角色/条件变化，可承担源获取主要验证。MAUD支持题级条款分类，Airline支持同政策复用，不能强行用它们证明跨法律规则变化。此次两个真实诊断失败已在扩大前暴露；不承诺通用数据集一定适合任何尚未实现的机制。

[完整性与费用证据](compositional_compiler_evidence/final_integrity.json)：143项相关回归通过；206项原冻结条目保持；9459条原账本记录逐行一致，新增调用0、模型使用新增费用0，电耗未计量。两项贡献均未获完整支持，Goal active、未完成。
