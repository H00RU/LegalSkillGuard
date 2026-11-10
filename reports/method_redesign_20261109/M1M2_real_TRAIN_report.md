# 当前结论：普通路径可用，两项独立方法仍未成立

最新工作是**0新增模型调用**的固定TRAIN响应清点与强普通控制。它补上原20来源之外的已有事实输出入口，揭示原21的规则引文冒充事实证据和原50的例外排除误读；分别可由已有引文合同/精确去重、官方结构化位置/原规则排除控制处理，未建立新学习机制。两项贡献仍未成立，Goal active、未完成。目标/验收/授权唯一见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，最新证据与下一项工作维护于[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。

上一真实验证新增1E/0T，原TRAIN3事实读取后缓存执行为E；原TRAIN83以旧事实/新目标路径执行为C，均匹配原TRAIN标签并有冻结重放。这些普通路径的证据继续保留，不能直接变成两项贡献。

## 正确缓存已具有什么

复用旧实际教师原响应，不重新生成法规：完整TRAIN3缓存包含A的终止后付款、死亡或残疾退休条件，并有覆盖其他条款的原程序。对A的三个条件枚举27项软件部分赋值，旧程序与对应布尔条件一致。只给原生注释支持的after/retirement两个正前提时，也能决定A；其他事件/计划保持未知。它不是27个法律样本、自动事实读取或新方法。

目标专用短教师程序与完整程序分开：短程序在旧全源接口下仍保留未翻译单元TOP，不忽略它们制造证书；这也不是给当前Goal追加每个模块都必须解析全部源码的门槛。旧教师两个生成都见过原案例/问题，不能称纯源、零提示或本轮新学习。

[实际旧缓存、27项软件控制及原生参考前提](train3_cached_condition_results.json) · [冻结原程序与执行](../../artifacts/rr_method_redesign_20261109/train3_cached_condition_control_v1_20261110/frozen_control.json)。

## 两条原来源的真实路径

| 原TRAIN | 模型/源程序的实际来源 | 当前执行 | 边界 |
|---|---|---|---|
| 3 | 新Qwen/OFF从原公共facts读三个既有谓词；规则来自旧完整教师程序 | after=true、retirement=true、death=null，旧缓存A查询输出E；原标签E；fallback0/1；冷重放一致 | 给定谓词API，不是执行器新生成全源IR；旧教师见过原案/问题 |
| 83 | 原direct:TRAIN83:original的payer=Alice/payee=Bob、work_is_agricultural=false；复用同部3306旧教师程序，代码只重新绑定原公开query的目标 | c(1)直接拥有s32的agricultural_labor_exclusion输出C；原标签C；fallback0/1；冷重放一致 | 新普通调用路径；旧路由错选记录不改，不将已有事实值或错误源代码改成答案 |

原TRAIN3的新事实模型没有看到原问题、标签、标注日期或参考证明，只收到原公共案情和实际缓存谓词/原文条件；生成91tokens，完整stop。给定的谓词与源代码不能再算成新学得接口。原0/89全源执行器IR失败分母及旧错误保持不变。

### 值正确和引文范围分开

模型把死亡留未知，未用缺失事实作否定；退休在公共案情直接出现。after=true与原生意图/既有参考证明一致，但模型引用的是“Bob被诊断残疾并退休”一句，没有单独覆盖付款时序。公共完整案情确已给模型，其中有“因终止合同而付款”的因果叙述；精确付款日只存在于另存原生标注，未输入或替换模型值。

因此记录为原生任务一致、存在引用范围缺口，**不称quote-only语义证书或任意自然语言蕴含保证**。也不事后新增“每条引文必须自含全证明/案情必须给精确付款日”的验收来抹去原任务结果。当前两项方法未成立，不用这一次答对替代其语义验收。

[原始事实值及执行前保存](../../artifacts/rr_method_redesign_20261109/train3_cached_fact_reader_v1_20261110/execution_before_cached_grading.json) · [实际发送内容、配置与冻结文件](../../artifacts/rr_method_redesign_20261109/train3_cached_fact_reader_v1_20261110/seal.json) · [原生语义/引文范围审核与恢复](../../artifacts/rr_method_redesign_20261109/train3_cached_fact_reader_audit_v1_20261110/native_review_and_replay.json)。

### TRAIN83的具体错选与修正

旧请求已经给出明确c(1)→s32地址，菜单同时列出s32的农业劳动排除和下层现金/工作日资格。模型却选了下层agricultural_employing_person_qualification。它是模型错选，旧调用器没有强制目标归属。当前普通选择器按原明确citation找唯一直接拥有目标单元的原声明；父条件仍由既有编译器继承。未按标签、名称相似或人工新规则猜答案；不同法条、含糊归属、其他问题形状均拒绝，不增加泛化兜底。

两个输出在原83家政案例上可以同答，不能据标签正确判语义等价。一个明确标作**软件完成**的条件组合让根排除为E、下层资格为C，证明它们不能互换；未把这个反例视为新法律样本。新实际路径复用原direct事实false、不改旧教师规则，通过当前原83预测与原缓存标签比较及冷重放；首次读取该原生标签视图记入账本。单一服务事件的已声明同义布尔适配和Alice/Bob角色核对由作者审核，不声称学习了任意多事件角色映射。

[源目标选择代码](../../experiments/rr_v2_cached_statute_target.py) · [原发送菜单与错误响应](../../artifacts/rr_method_redesign_20261109/cached_statute_target_control_v1_20261110/actual_old_route_input.json) · [执行先于评分、旧事实/程序、软件反例](../../artifacts/rr_method_redesign_20261109/cached_statute_target_control_v1_20261110/execution_before_original_cached_grade.json) · [结果和原生评分](cached_statute_target_results.json)。

## 固定TRAIN响应清点和新增普通控制

读取原固定128个TRAIN来源键对应的1215条已完成执行器响应，另1条失败仍计费。响应有53种JSON顶层形状；35条含命名事实值，共255行、30个账本主来源。加上局部角色、事件、批量case和金额span等，共74条事实型候选响应、37个主来源。重复请求、混合source/fact响应、同一母来源变体及批量响应分别保留，不能换算成独立native样本、接受IR或新增训练数据。

该清点没有把程序中的观察声明当成实际读取值，也不以外层code/IR桶排除其中所有可能可用的嵌入信息。472条非JSON记录含合法的原始Python文本，不把这个数当新截断/失败统计；原89条记录与分母不改。旧20来源审计也不外推到全部128。

原OpenExempt TRAIN21是新展开的实际例子：八个false值分别引用联邦/州法服装条文，而非案情，已有精确事实引文检查就会拒收。它们不经修补变成true。按完整语义输入（entity、predicate、fact_text、predicate_context、reference_years）做普通精确去重，可把八个输出槽合成四组；没有擅自把不同法域的同词含义合并。**输出槽减半不是物理调用/耗时减半，也不是核心学习。**

原Airline TRAIN50把首行明确排除Peru的地理条件返回true。只读取已核验官方gen_questions.py的城市映射常量，可知原Orlando→Lima为U.S.→Peru；配合原请求中该谓词的明确排除，就得到必要条件false，无需费用答案或新教师标签。此控制只驳斥这一行，未把未触犯排除的其他行都判正确；原模型输出、旧IR/得分不改，不宣称完整费用计算恢复。

[清点与最终控制结果](recorded_fact_inventory_with_controls_results.json) · [逐物理响应形状清单](../../artifacts/rr_method_redesign_20261109/recorded_fact_inventory_v1_20261110/frozen_inventory.json) · [原21请求、八个原错值和精确去重](../../artifacts/rr_method_redesign_20261109/recorded_fact_inventory_v1_20261110/original_OE21_provenance_and_exact_dedup.json) · [普通源位置/排除控制](../../artifacts/rr_method_redesign_20261109/recorded_fact_inventory_v1_20261110/ordinary_native_location_exclusion_control.json)。官方代码固定在[RuleArena原提交](https://github.com/SkyRiver-2000/RuleArena/blob/59f60f6b4eb93a9b6d187ec781349d4f15618903/airline/gen_questions.py)，只抽取城市常量，未执行题目生成或读取生成数据。

这为后续机制提供了更完整的已有入口，**没有证明其余字段已解决或所有研究方向都不可能**。当前“源谓词分解/共享或噪声校正”仍须面对fact-only、精确语义输入去重及结构化事实后执行源条件这些强控制，不因存在一个神经读错就拟合新模型。也不新增所有255行逐条全对的Goal验收。

本次模型/标签视图/来源/配对新增均0，账本1467calls/228meta/137oracle逐行与快照一致，累计1399E/68T、pending0；API现金增量0。无DEV/TEST、完整建库/矩阵、主训练或论文，main未改。下述1E费用是上一真实验证，不能重复计费。

## 方法判断、调用与费用

正确缓存计算、静态依赖、精确目标选择和既有直接事实读取已足以完成这两条普通路径；不能把它们拆成两个创新，也不能将源程序仍未自动学得的新机制描述成已经完成。当前没有依据为这两个成功来源重复购买相同修复；剩余研究必须有未被强普通控制吸收的具体学习/更新作用，必要DEV/迁移也仍缺。没有启动主训练、完整建库/矩阵、DEV/TEST或论文。

上一真实验证的新执行器501输入/91输出tokens、2.489秒，wire明确OFF、reasoning_content=null、temperature0.6/top_p0.95/top_k20/seed45/max_tokens8192及客户端重试0不变；非缓存，新增API现金0。教师新增0，旧缓存获取费用不抹去；GPU分摊、教师实际发票和项目总费用未知。

原1466calls/226meta/136oracle逐行保留，新增1 calls、2 policy meta和1个原TRAIN83缓存标签视图；无新增反事实、数据来源或原生配对。累计 **1399E/68T、pending0**，1467/228/137，账本另存前后快照。本轮新模型原生预测/缓存评分1（TRAIN3）；原模型事实在新调用路径重执行/评分1（TRAIN83），不是两个新模型生成、更不是两项贡献。main未改。

[真实读取/费用/完整账本核查](train3_cached_fact_reader_results.json) · [请求与原标签视图差量](../../artifacts/rr_method_redesign_20261109/train3_cached_fact_reader_audit_v1_20261110/request_and_view_ledger_delta.json)。

---

以下均为保留的历史科学证据；旧状态与“下一步”不覆盖当前两份维护文件。

# 历史证据：普通基线完成两条原生调用，方法贡献仍未成立

**本次新增1E，锁定Qwen/OFF在原111/115问题上实际选择缓存调用并执行，两条均与原生TRAIN标签匹配；无回退，冻结重放一致；事后固定任务选择器也在0新增模型请求下复现2/2。这里打通的是普通源缓存的使用链，不是执行器独立源规则生成、两项方法贡献或整体训练就绪。** 授权/验收仍仅见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前缺口与下一步只见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。

## 最新离线核对：原TRAIN3的子条件与整项豁免

新增模型调用0。只加载原固定TRAIN3的原始事实、未改写的原生法条和原始目标s3306_b_10_A("paid",_,_,_,_,_)，SWI-Prolog实际返回雇佣关系、Bob、Alice、终止事件与残疾原因见证，与已缓存原TRAIN标签Entailment一致。原生A规则不依赖B计划；B出现在整项b10规则中，不能把完整豁免的计划条件追加为原A问题的验收。

两条已付费Qwen响应均完整stop，却将1000元、2019个案常量或非家政/农业条件写成A规则，属于模型语义错误，原拒收不变。已有目标专用教师程序已表示“雇主付款且残疾退休终止”普通条件；它见过案例/问题，不算新的纯源获取、方法优势或本次模型执行。原生标注中的2019-10-10付款日也不冒充公共文本的自动抽取。

这次补足查询口径和实际错误定位，不新建案例/假设，不执行新整项豁免问题，不把原生参考重放计作模型主路径或新有效全源IR。账本仍1398E/68T、pending0，1466calls/226meta/136oracle逐行不变；没有新增DEV/TEST或完整训练。

[结果及账本核查](native_subclause3_results.json) · [实际原生见证、旧错误响应与教师对照](../../artifacts/rr_method_redesign_20261109/native_subclause3_audit_v1_20261110/evidence.json) · [离线审计实现](audit_native_subclause3.py)。

## 实际生成与确定性编译分别做了什么

源程序、4个谓词、角色、例外定义及完整ground calls由上轮1T从两份合同取得。执行模型本次只看到原生问题、实际接口含义、源引文和两个可用调用；不提供原生标签、正确选择或旧响应。模型输出每个policy的entrypoint与positive；ground arguments由所选真实源调用确定性拷贝。null入口会记录未绑定，不默认到任何调用/NotMentioned。

实际响应完整stop，共74输出tokens。两个绑定都选择contract_states_conditional_reverse_engineering_prohibition及positive=true，没有把问题中的shall not再次取反；未创造授权事实。随后使用原冻结普通law_cache实际执行，不从标签、旧结果或回退取答案。执行先保存，再复用已见TRAIN缓存评分，属于已知TRAIN可行性验证而非新盲测。

| 原TRAIN | 实际模型选择 | 实际代码输出 / 原标签 | 本次回退 | 结果范围 |
|---|---|---|---|---|
| 111 | 规范存在入口，正向 | Entailment / Entailment | 无 | 原生规范性读法；参数来自源缓存 |
| 115 | 规范存在入口，正向 | Entailment / Entailment | 无 | 原生NLI读法；保留源samples/prototypes/products范围，不声称其与假设所有对象域逻辑等价 |

[真实请求/响应与执行前记录](../../artifacts/rr_method_redesign_20261109/contract_norm_binding_v1_20261110/execution_before_cached_grading.json) · [提示、配置、实际API及封存输入](../../artifacts/rr_method_redesign_20261109/contract_norm_binding_v1_20261110/seal.json) · [绑定实现](../../experiments/rr_v2_contract_norm_binding.py)。

## 语义、恢复与覆盖

原问题是合同规范性陈述，不询问某次授权事件是否发生；所选入口/极性按此原生口径核对，例外条件仍保留在源程序的适用性分支中。该分支在原生两问中没有被调用，其16项软件控制及4项作用域控制属于上轮证据，不把它们重记为本轮真实事件推理。

写入包含源代码、API、模型选择、原问题及源范围的冻结bundle，冷加载后重编译调用并实际执行，与原始输出逐项一致。原生标签复用已见缓存；既没有把数据改成严格FOL任务，也不将标签正确等同于全对象域/全合同的语义等价证书。

当前仅尝试2/24个原固定NDA来源，成功名单111/115，fallback为0/2。其余22条没有进入这个双合同缓存，单独记为未尝试；不伪称回退成功、模型错误或已解决。120的较宽use解释桥仍未解决，不据一个TRAIN正例补法律规则。未验证其他四个基准或新方法跨库作用。

[两条原生评分、视角审核与冷重放](../../artifacts/rr_method_redesign_20261109/contract_norm_binding_audit_v1_20261110/native_grades_and_replay.json) · [原24来源完成状态](../../artifacts/rr_method_redesign_20261109/contract_norm_binding_audit_v1_20261110/original24_source_status.json) · [可重复审计](audit_contract_norm_binding.py)。

## 最简单任务配置对照

两条原问题是同一个冻结假设，源获取时已要求提供对应的规范性入口。补充一个事后普通对照：不读取Qwen选择，按给定任务/源路由元数据选择该规范性入口，再实际执行同一个已付费源缓存；两条输出都与真实Qwen调用和原标签相同，新增模型请求0。它没有直接返回字面答案，也没有免除原1T源获取成本。

这是同两个已见TRAIN案例上的事后分析，不是新盲测、对其他假设的通用适配或整个NDA任务的0模型解法。它已经吸收本小试的调用选择效果，因此不再为这两个样例追加同类路由或直接回答模型请求。初始模型审核结果未覆盖，新增控制另存with_selector结果。

[事后选择器实际执行](../../artifacts/rr_method_redesign_20261109/contract_norm_binding_audit_v1_20261110/posthoc_task_bound_selector_control.json) · [保留的首版审核](contract_norm_binding_results.json) · [含新对照的审核](contract_norm_binding_with_selector_results.json)。

## 方法判断及后续

普通缓存已具有源获取、元规范/具体适用区分、实际Qwen调用及恢复证据，不能将这些公共组件改名拆成两个创新。本轮没有学习查询视角定义、实参角色、事件读取或例外子条件组合；源规则由教师生成，Qwen只路由调用。旧89条全源IR失败不改，不把新调用选择计入其分子。

两项具有独立作用的机制及必要DEV/跨库证据仍缺。已有普通缓存、直接抽取/检索与普通学习器均是后续必要强对照；没有具体增量依据前，不再重复这两个成功样例或扩大完整建库/矩阵。12配对提案未授权、未执行；本次成功不触发旧计划，不新增零回退/全类别/涨分验收。

## 账本与实际费用

新增1E/0T；1460输入/74输出tokens、2.196秒。真实wire明确enable_thinking=false，响应reasoning_content=null、stop；temperature0.6/top_p0.95/top_k20/seed45/max_tokens8192未改，重试0。源获取之前1T为19918/5164tokens、107.448秒，两步请求耗时合计109.644秒；它们承担不同模型/生成目标，不据此宣称因果速度优势。执行器新增API现金0；GPU分摊、教师实际发票及项目总费用未知，教师供应商内部重试仍不可观测。

原1465 calls/225 meta逐行保留，新增1 calls/1 policy meta；136 oracle不变。现1466calls/226meta/136oracle，累计**1398E/68T、pending0**，另存前后账本。新增2项原生预测评分复用原TRAIN缓存，没有新标签、来源或配对；未打开DEV/TEST、启动主训练/完整建库/矩阵或论文，main不改。Goal active、未完成。

[汇总/成本/累计核查](contract_norm_binding_with_selector_results.json) · [本轮真实请求账本差量](../../artifacts/rr_method_redesign_20261109/contract_norm_binding_audit_v1_20261110/charged_delta.json)。

---

以下是历史证据；旧状态/计划不覆盖当前两份维护文件。

# 历史证据：普通源缓存的真实获取与两种查询视角

**本次新增1T，真实从原111/115公开合同取得4个谓词及普通缓存代码，完成执行、条件审核与冻结重放。现有普通组件已能区分“合同规定一项条件性禁止”与“该禁止在给定事实下适用”，无需另造IR。这是实际源获取产出，不是两项方法贡献；Goal active、未完成。** 执行边界只见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前证据与下一步只见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。

## 输入、实际学得内容与给定部分

一次教师获取仅给原111/115两份完整公开合同；不提供原生问题、标签、案例事实、旧响应或正确程序。提示明确聚焦reverse engineering，并给定“规范存在/具体适用”两种查询含义、签名原子/普通Python调用合同和返回值含义。这些目标与视角是作者提供的共同任务接口，不声称零提示、模型发现原生注释口径或方法学习成功。

模型自选4个谓词及有序角色、两份源规范原子、各自的完整例外原子和普通law_cache代码。111的例外含Discloser特定授权、事先和书面；115含行为pursuant于双方接受、书面并由双方执行的协议。两个源引文均为各自合同精确子串，没有补写模型原文或改规则。

普通代码将规范原子与具体适用查询分开。前者从真实源规范获取支持；后者读取明确签名的完整例外事实。规范性查询在例外事实缺失时仍Entailment；适用性在缺失或冲突时Unknown，明确例外适用时只否定该条禁止的适用，不推出行为被所有法律/条款允许。

[原始模型响应/谓词/代码](../../artifacts/rr_method_redesign_20261109/contract_norm_cache_v1_20261110/source.json) · [实际提示及封存输入](../../artifacts/rr_method_redesign_20261109/contract_norm_cache_v1_20261110/seal.json) · [普通获取入口](../../experiments/rr_v2_contract_norm_cache.py)。

## 执行和边界

16项执行来自2合同×2查询视角×4软件例外状态（未知、适用、明确不适用、冲突），均匹配该源模块的控制预期。另4项核对不串用他份合同的例外、不把不匹配的授权者/相对方当成本合同完整例外。写入普通JSON缓存后，冷加载按同一原代码重放逐项一致。

这些都是软件上下文，不是新增原生案件/假设或反事实oracle。未将原生问题自动映射到模型API，也没有事件阅读器、执行模型新IR或新的原生评分。完整例外仍被封装为复合输入谓词；程序不独立识别每个子条件或从部分事件自动计算法律例外。原生查询的protected subject范围也未由新模型mapper验证；不能将元数据路由当作新的完整端到端NLI成功。

[有限源审核](../../artifacts/rr_method_redesign_20261109/contract_norm_cache_audit_v1_20261110/source_semantic_review.json) · [冻结缓存](../../artifacts/rr_method_redesign_20261109/contract_norm_cache_audit_v1_20261110/frozen_ordinary_cache.json) · [冷重放及作用域控制](../../artifacts/rr_method_redesign_20261109/contract_norm_cache_audit_v1_20261110/frozen_replay_and_scope_controls.json) · [可重复审计](audit_contract_norm_cache.py)。

## 决策

本次直接复用了既有普通代码运行器，没有新增deontic框架、生产类型或旧接口兼容包装。它成为后续候选必须面对的普通强对照；不能把两个查询视角、4个谓词、源缓存或软件检查数拆成两个创新。旧原型/源契约/年度程序的否定证据全部保留，不重跑已被等价控制吸收的功能。

研究缺口进一步限定为学习本身：可靠的源解释、实际证据绑定或可复用解释关系如何取得，以及能否超出同信息普通源缓存/直接模型/检索/普通学习器。当前没有这两项独立作用，不能扩大完整建库或宣布训练就绪。12配对仍未授权/未执行，也不因本次普通组件成功自动启动旧计划。

## 实际费用与累计账本

本次1T可见attempt1、非缓存、无工具事件；19918输入/5164输出tokens，3171 reasoning为输出子集，107.448秒。教师原模型/high、显式温度未设置、客户端重试0不变；供应商内部HTTP重试不可观测。没有新执行器请求，OFF配置未变。执行器API增量现金0；教师发票、GPU分摊及项目总费用未知。与旧失败调用的模型、目标和范围不同，不据一次耗时宣称因果成本优势。

原1464 calls/224 meta逐行保留，新添1 calls/1 policy meta；136 oracle不变。现1465calls/225meta/136oracle，累计**1397E/68T、pending0**，账本另存前后快照。源码和协议在真实请求期间冻结；未新增来源、原生评分、DEV/TEST或主训练/论文，main未改。原Goal未完成。

[汇总结果、费用及账本核查](contract_norm_cache_results.json) · [实际新增请求](../../artifacts/rr_method_redesign_20261109/contract_norm_cache_audit_v1_20261110/charged_delta.json)。

---

以下是历史证据；旧状态/计划不覆盖当前两份维护文件。

# 历史证据：原生规范性查询口径与固定任务普通控制

**本次没有新增模型调用。先冻结一个普通词面控制和解释探针，再核对原24个ContractNLI TRAIN缓存标签：控制23/24，标签为3个Entailment、21个NotMentioned、0个Contradiction。111/115含授权例外仍被原生任务标为Entailment，说明必须区分规范性假设与事实事件执行；这不是新的核心学习成功，两项独立贡献仍未成立。** 目标/验收/授权仅见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，最新缺口与下一项工作仅见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。

## 原数据范围内的实际受控核查

控制在读取标签前写入不可变工件：命中reverse-engineer/decompile/disassemble词形则预测Entailment，否则NotMentioned。未按标签调整词表，未添加文档、假设、来源或反事实。随后只选原24个TRAIN nda-11缓存标签评分，未读取DEV/TEST标签。它是一个故意简单、没有一般NLI保证的对照，23/24不等于机制或整体就绪；也不把缺少Contradiction新增为验收失败条件。

另在看标签前固定三个作者解释探针：条件性禁止规范存在时Entailment、要求所有未知事件完成均禁止时Unknown、用任一可行例外反驳无条件禁止时Contradiction。这些是作者诊断抽象，不是模型输出或正确源程序，没有真实学习/自动解释证书。

[审计实现及分开的prepare/grade/evidence阶段](audit_contract_native_query_labels.py) · [看标签前的不可变预测](../../artifacts/rr_method_redesign_20261109/contract_native_query_profiles_v1_20261110/predictions_before_labels.json) · [24条结果与解释探针](contract_native_query_label_results.json)。

## 原生证据说明了什么

111/115均标为Entailment。只打开原始TRAIN成员，精确匹配文档hash、原文假设ID、choice及证据span，确认缓存未错位：对应证据正是带书面授权例外的逆向工程禁止。原生问题询问合同规范，不是在问授权是否已发生；不能把未决授权事件枚举后的Unknown，或任一可行例外直接产生的Contradiction，强行当成该原任务唯一正确解释。

这修正的是验收解释，不放宽程序检查。原111/115的重复声明、query来源冒充规则、问题字符串产标签、截断及源条件丢失等记录仍保留。一个忽略例外的固定No即使匹配原生标签，也不是完整源规则保真证明；同样不能把所有条件不明的规范性原生判断都改判失败。

唯一词面漏例是120：原生标签Entailment，证据为一条未经书面批准不得publish/copy/use for sole benefit的较宽限制。该句没有词面reverse-engineering。它说明直接找目标词不覆盖原任务解释，但不能据此补造通用use→reverse-engineering法律规则。原固定首四NDA中的5/15/20也有不同的use限制，原生标签为NotMentioned；这些文本与120并非完整语义等价，不能从局部相似断言注释错误。未事后修补预测器，未将原生证据输入模型或写入新规则。

[原生TRAIN证据、精确位置、hash及use边界](../../artifacts/rr_method_redesign_20261109/contract_native_query_profiles_v1_20261110/original_native_evidence_and_scope.json)。

## 对机制设计的约束

[ContractNLI原研究](https://aclanthology.org/2021.findings-emnlp.164/)将其定义为文档级NLI并使用针对固定假设的注释指南；不能把它缩成句子存在检测。[Know Your Limits](https://arxiv.org/html/2606.16118v1)明确通过重标来评估严格逻辑蕴含；这里保持原标签。[COMPACT](https://aclanthology.org/2026.eacl-long.377/)已有主体/模态/动作/对象/时间和定义、例外、依赖等图关系，因此这些字段和边本身不能再拆作两个贡献。

下一问题是源规范与任务解释如何分离并学习：保留条件/角色/动作，又不把任务标签硬写进法律规则；区分规范性查询与事实执行。当前还没有超出普通源缓存、直接NLI、检索和同信息普通学习器的具体机制。已有开关、SAT和公共接口修复不能替代这一差异；仍须真实主路径、独立作用及必要开发/恢复证据。12配对提案未授权、未执行，即便许可到达，也不自动购买旧计划小试，更不据此完成Goal。

## 账本、隔离与状态

本次新增模型原生预测0、物理请求0、反事实oracle0；实际完成24项原缓存TRAIN控制评分、6项作者解释探针比较，核对3条原始TRAIN证据。它们不是24个新来源、模型实证或新的完整评测矩阵。calls1464、meta224、oracle136逐行与原备份一致，累计1397E/67T、pending0；原标签未重定义，未碰DEV/TEST成员或启动主训练/论文。新增API现金0，历史教师发票和GPU分摊未知；main未改，Goal未完成。

---

以下是历史证据；旧状态/计划不覆盖当前两份维护文件。

# 历史证据：调用不兼容修复与普通控制覆盖

**本次0E/0T，继续了原固定TRAIN上的离线研究。发现并修复两处具体工程问题：原型缺少动作绑定、公共布尔投影调用与说明不一致。独立普通缓存覆盖现有原型的全部已声明软件语义，因此没有把这两项修复/软件开关算成两项贡献。Goal active、未完成。** 目标/验收/授权只见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前缺口与下一项工作只见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。

## 真正增加的证据

原型只接受recipient，未接受查询action：隔离软件fixture中，逆向工程许可会错误支持保留信息，逆向工程禁止会错误否定保留信息。现要求规则和查询显式匹配action，不加别名或猜测；两类反例都恢复Unknown。义务仍明确拒绝，不把permission/prohibition原型冒充完整合同语义。9项相关回归通过，修复前源码和反例保留。

独立普通对照把角色定义作有限关系连接，将守卫物化为真值表，不调用候选的定义展开、分类或一致性函数来生成对照答案。在2个软件布尔变量的全部16种正守卫、16种负守卫、2种角色、2种模式与9种部分上下文上，共9216项输出相同（Entailment3504、Contradiction642、Unknown5070）。普通一致性学习在软件约束上也选出同一possible模式。

这只覆盖声明的微型域，不是9216个法律样本，不证明自然语言源获取或原生NLI语义；有限表达能力相同也不排除未来获取可靠性或成本作用。它已经足以说明：当前原型的字典/SAT/选模没有额外学习机制，不能拆作两个已实证贡献。

[独立控制实现](audit_norm_query_controls.py) · [完整结果](norm_query_control_results.json) · [动作修复回归](norm_query_action_binding_regression.txt) · [修复前后工件](../../artifacts/rr_method_redesign_20261109/norm_query_control_audit_v1_20261110)。

## 固定111/115的真实失败，与当前原型问题分开

检查同一账本中reference-v8已有4次执行器请求，逐字核对发送body、原始响应及OFF配置。使用与旧seal一致的pal_frontend/source_code源码回放；未读取原生标签、未调用oracle、未生成新查询。

| 原TRAIN/尝试 | 完成原因 / 输出tokens | 精确拒收与其他可见问题 |
|---|---|---|
| 111/0 | stop /215 | 普通布尔比较无法进入entailment_label的图路径；另有重复函数、query来源冒充规则、固定No忽略例外 |
| 111/1 | length /8192 | 重复展开后语法截断；不能补齐缺失语义 |
| 115/0 | stop /71 | 同一投影调用问题；对问题字符串检查reverse-engineer而不检查合同，常量条件为false，另以query作规则来源 |
| 115/1 | stop /573 | 重复city_state_zip/name/title/signature声明及无关标签常量，query来源仍被用作规则 |

因此这4条中3条完整、1条截断；不据这个局部比例修改旧89条的约96%截断记录，也不推断模型普遍无能力或现有输入不足。当前玩具原型的action缺陷并不是这些历史失败的原因。

原发送runtime_contract确实说明entailment_label为Boolean到Entailment/Contradiction投影，但解析器只允许将其包在connector graph上，普通比较/已声明规则调用无法使用。这是接口说明与可执行路径的不一致，不能把函数名说成模型凭空发明。现将普通布尔表达式确定性降为既有if，图/slot投影仍走原路径；类型器继续拒绝字符串条件，未决布尔仍有两个完成，不默认NotMentioned，也不补来源或规则。

30项相关回归通过（含原有完整前端控制）；第一次新测试误把ScopedQuery当callable并捕错异常类，失败日志保留，随后只修正测试调用为evaluate和实际IRTypeError。4条旧响应在新解析器下仍因其余错误拒收；此修复不是无损恢复全部原始输出，更不是新的原生成功。

[历史真实响应与冻结解析器核查](audit_recorded_contract_failures.py) · [逐请求结果](recorded_contract_failure_results.json) · [接口修复前后](../../artifacts/rr_method_redesign_20261109/recorded_contract_failure_audit_v1_20261110/projection_interface_repair.json) · [30项回归](pal_boolean_projection_regression.txt)。

## 决策与费用

继续以原固定来源的条件丢失、动作/角色和查询常量污染为依据形成可检验机制；普通源缓存、定义查找、直接NLI和同语法普通学习不能被排除。当前仍缺实质差异、真实源获取及独立作用，未进入完整建库/矩阵。12配对提案仍未授权、未执行；它不再被写成整个Goal唯一阻断。即使数据许可到达，也不会据旧计划自动发2T/6E，因为数据许可不等于方法必要性。

累计仍1397E/67T、pending0；1464calls/224meta/136oracle逐行与前一备份一致。新增模型、原生评分、oracle、配对及API现金均0；上述4次历史调用早已记账，本次不重复计费。项目GPU分摊和教师历史发票仍未知。原服务未改，未启动主训练、完整评测矩阵、TEST或论文。main不改，Goal未完成。

---

以下为历史研究证据；旧候选、下一步及调用计划不覆盖当前两份执行文件。

# 法律技能学习：作用范围、真实执行与强对照证据

## 历史证据：3306作用域与固定任务覆盖审计

**本次0E/0T。已执行原生3306作用域子句，确认普通子条款缓存足以表达该区别，不把scope标签晋升为贡献。另核实当前ContractNLI被预先限定为同一个nda-11假设；新的合同定义/模态候选尚只有软件原型，未有真实方法实证。两项贡献仍未成立，Goal active、未完成。** 目标和授权仍只见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前状态见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。下面12配对是待决定提案，不是已授权实验。

### 3306：信息必须保留，不等于需要新方法

从既有SARA归档只读取section3306.pl，SHA256为`6d283f999cfb578d704aa5586a593dd78b89b834006d4277af81f2008a094455`，没有读取原生case/goal/label。其实现已把3306(a)(1)、(a)(2)、(a)(3)保持为不同谓词，并明确将(a)(4)作为由这种分离保证的不变式。a4的零参数true是该实现的元约束，不是任意个人都具有雇主身份。

实际调用既有SWI运行6条未改写原生子句。隔离fixture以原73的两条付款方向和服务身份为依据，把工资准入、付款年、媒介留作软件完成变量；`s3306_b`在此只是一张准入输入表，不声称已计算完整工资/雇主条件。192种完成下，Alice的一般工资分支和一般雇佣日见证均不成立；家政状态在某些完成下成立，Bob的反向付款不计入Alice。SMT另证明一般工资和在所有准入/期间布尔完成下为0，并给出错误“任一类雇主身份都通用”的反例。

这些完成不是192个新案例，没有填入原73缺失的付款日/现金事实，没有开新标签或原生评分。最初fixture把含阈值守卫的Prolog关系当成总金额函数，正确的关系失败导致probe退出；调用已改为观察关系成功/失败，没有修改原生子句。

这说明作用范围确实重要，也说明普通按子条款拆分的缓存已经能够保留它。**金标准参考重放不证明模型已自动学会**：现有学得3306程序只覆盖年度b1组件，完整a/b/c的获取仍未完成。但在没有独立机制差异前，不为这个表示候选再购买同目的生成，不重跑年度cap与付款去重。

[可执行核查](audit_3306_scope_reference.py) · [结果](legal_3306_scope_results.json) · [原生子句、原始stdout与全部软件完成](../../artifacts/rr_method_redesign_20261109/legal_3306_scope_reference_v1_20261110/native_reference_and_fixtures.json)。

### 最近邻进一步收紧了可声称的差异

[Catala](https://book.catala-lang.org/en/5-3-scopes-toplevel.html)已有scope/context与例外；[SG-DT/NormBench](https://arxiv.org/html/2606.08932v1)已有跨度锚定、显式排除和例外挂接，因此这些环节本身不算新贡献。[原ContractNLI研究](https://aclanthology.org/2021.findings-emnlp.164/)已讨论定义引用和例外否定；[Know Your Limits](https://arxiv.org/abs/2606.16118)则用重标后的严格逻辑任务区分法律解释与形式蕴含。

候选若继续，应保留原生任务解释和标签，把具体的定义绑定与查询模态处理写为可检查的执行接口。不能偷偷重标ContractNLI、给所有缺失事实设false，或修改假设来使结果通过。下面是尚待证实的机制差异，不是已经找到两个创新。

### 当前固定任务的真实覆盖边界

`adapters.contractnli(..., hypothesis="nda-11")`是调用模型前的明确设计；24 TRAIN与8 DEV均为“Receiving Party shall not reverse engineer any objects which embody Disclosing Party's Confidential Information.”。这不是适配器随机漏题，也不将覆盖全17个假设新增为Goal验收。

仅原111/115有reverse-engineer/decompile/disassemble词形命中，其余22条无这些词形；词形统计不是标签分布，不能据此判为NotMentioned。先前首4来源5/10/15/20均无该词形，不适合用它们声称验证了其他合同权限/例外机制。原论文和旧报告中的“ContractNLI”结果应按这个固定单假设任务理解。

本次只机械解析TRAIN/DEV原始JSON以投影假设文本、文档ID和正文hash；没有选取、返回、拟合或评分annotation choice/evidence标签，没有打开TEST成员。原128包、数据划分和oracle账本不变。

[覆盖/源定位审计](audit_contract_hypothesis_coverage.py) · [覆盖结果](legal_scope_task_coverage_results.json)。

### 两项候选设计卡：必要性有具体来源，独立作用仍未知

| 设计项 | 候选一：定义相对的授权见证 | 候选二：原生模态查询的执行方式学习 |
|---|---|---|
| 真实问题 | “Representatives”可能包含员工、外部顾问或两者；分享给该集合不等于任意第三方，也不能只匹配名词 | “可以在某些情形下”询问是否存在可授权条件；把它当成条件已实际发生会漏掉许可。缺少许可也不等于禁止 |
| 拟实现 | 从真实源定义编译角色域，许可/限制与查询必须绑定同一角色域；给出域内授权见证或明确的阻断原因 | 固定一组有语义区别的查询执行方式，用TRAIN约束学习其适用性；原始假设、选用解释和执行轨迹均保留，不能按DEV答案改查询 |
| 最近邻区别 | ContractNLI已知定义引用，SG-DT已有源树；拟补的是跨定义—许可—查询的可复用绑定及见证检查，不能只给树加字段 | Know Your Limits重标严格任务；这里不换原生标签，拟学习并显式记录查询解释。不是声称SAT或一致性筛选全新 |
| 最强简单对照 | 同信息直接NLI/角色抽取、定义查找、普通正确政策缓存、源树/SMT，以及去掉定义绑定的消融 | 同材料检索、普通程序缓存、同语法一致性学习器、固定执行方式及去掉学习的消融 |
| 已有最小原型 | 定义展开使角色见证可成立；不展开时保留Unknown，未默认禁止 | 对条件许可，可能情形查询与实际条件查询产生不同结果；未知/正负冲突保留，普通一致性选择能复现软件标签 |
| 关键未知 | 模型能否从真实合同取得正确定义/关系；是否超出普通定义查找/缓存 | 原生标签能否识别稳定解释；是否只是普通选模换名。若是，不能计第二贡献 |

原型用的都是作者软件fixture，字典展开、SAT和普通一致性学习器都是公共基础，不算真实学习或方法优势。7项相关检查通过，包含缺失不置false、无序冲突及未知效果拒收；没有取新增标签或做模型调用。该原型既不证明ContractNLI语义完整，也不证明两项贡献成立。

[软件原型](../../experiments/rr_v2_norm_query_prototype.py) · [软件探针](../../artifacts/rr_method_redesign_20261109/legal_scope_task_coverage_v1_20261110/software_semantics_probes.json) · [7项检查](norm_query_prototype_regression.txt)。

### 可审阅的数据范围调整提案，尚未执行

为检验这两个候选的独立作用，建议只补12个原生文档—假设配对，不增加文档或数据集，不替换原128来源：

- 8 TRAIN：原文档5/10各增加nda-5（共享员工）、nda-7（共享第三方）；原111/115各增加nda-16（返回/销毁部分信息）、nda-20（保留部分信息）。选择依据为原固定文档与假设类型，未看新配对标签，不按结果补齐类别。
- 4 DEV：原DEV中按source ID排序的前两文档，各增加nda-7、nda-20。文档分组与TRAIN不交叉；只在实现/库冻结后做一次对应验证，不回灌学习。
- 原TEST不动，旧24/8的nda-11结果与原五库、代码、原始失败和累计账本全部保留。新配对将是独立补充小试，不改写原预注册分数。

计划的首个真实比较预估2T/6E：两份独立TRAIN获取用于候选和普通缓存，固定共享可见TRAIN材料；候选、普通缓存、直接/检索三臂分别在两个假设家族批次执行。原模型/采样、OFF、资源授权与累计账本沿用；这是计划规模，不新增机械全局上限或逐轮索权。失败/重试均持续记账，只有有明确修复和离线依据才真实重试。若强对照吸收效果或这批任务没有辨别力，如实报告，不为涨分追加样本/种子/提示扫描。

这是候选路线的范围申请，不是原Goal天然必须扩数据或新增验收标准。若维持原池，就不执行这12配对。它们确实超出原冻结的nda-11配置，因此需要用户决定数据范围；当前没有实例化新Source/推理包、没有把其标签作为oracle读取或用于学习、没有分派新请求。**数据获准和小试成功都不等于Goal完成**；仍须两项机制各自有真实主路径、语义证据、强对照下作用及必要开发/恢复验证，不额外要求零回退或涨分。

[12配对完整清单，状态为NOT_AUTHORIZED](../../artifacts/rr_method_redesign_20261109/legal_scope_task_coverage_v1_20261110/proposed_native_pairs_NOT_AUTHORIZED.json)。

### 本次计数与阶段状态

累计仍**1397E/67T、pending0，1464calls/224meta/136oracle**，各行在本次离线核查前后相同。新增模型、原生评分、oracle和源包均0；SWI软件完成和软件原型不计模型实证。原服务身份未改，无生成客户端。GPU分摊、教师历史发票和项目总费用的未知状态保留，不能报总费用0。未启动主训练、完整矩阵、TEST或论文。Goal保持active、未完成；本候选的下一次实际验证依赖上述数据范围决定，不恢复旧额度或修复轮次限制。

---

以下均为历史研究证据，不覆盖两份当前执行文件。

## 历史证据：源证据标准真实学得，关键残余被简单控制处理，本方案不晋升贡献

**本轮已实现并真实验证了从原法条/API取得输入证据标准的路径。教师表减少了部分错误，但没有消除关键dependent误读；普通API/引文隔离控制用0次新增模型请求完成相同来源的正确重执行。因此不以这个方案成立独立贡献，也不扩大同例生成或建库。两项独立贡献仍未建立，Goal active。** 目标/验收/授权只见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前证据和下一项工作只见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。

### 从人工指导推进到真实源获取

原普通fact-only的3/3使用了明确的基础概念指导。本轮源获取只见既有151/152法条与真实15谓词API，不见81/86/72事实、问题、标签、旧错误—修复或手选法律输入谓词名单。原API和规则获取成本继续保留，本轮不是重新从零学API。

第一条Qwen源响应完整stop、2675输出tokens，未截断，但仅14/15项，全部14条引文包含改写/新增标题或空串，10项把同一长陈述同时写为直接及非充分证据；exemption_amount的描述没有金额值。这同时含表示/契约问题与模型语义错误，不能只补名册或规范空白后称恢复成功。坏表未进入读取。

修复改为真实API固定键、原文段落编号及确定性引文恢复，并区分“直接断言该状态”与“足以推导状态的规则前提”。9项回归包含真实失败陈述的矛盾检查。源编译由原已授权教师执行，模型/high/显式温度未设置不变；执行模型仍Qwen3-8B、OFF。教师和表示同时改变，不能据此分离模型能力与格式负担的因果效应。

真实教师返回15项直接/非充分证据标准与原文段号，未见案例。原文字符位置逐段核对，未人工改写任何表项。审核只批准有限读取验证，不称整份自然语言契约完整：全条款引用别名、严格定义换说法与可撤销推导仍有过度保守风险。教师表和这些未决均封存。

### 普通源文搜索、自审和新指导分别真实执行

两份普通提示在新教师响应前封存，普通臂得到完整源文/API，可自己构造定义表，不被限制为字面匹配；自审还见自己的真实frame、一般失败类型和实际规则头名单，但没有正确frame或候选教师表。guided只见源表/API/相同事实，三臂都不见问题/答案，沿用旧查询与公共年度/身份任务adapter。

| 实际读取 | 原生标签匹配（既有TRAIN） | 符合本实验直接前提通道约定 | 已核实为假的法律断言 |
|---|---:|---:|---:|
| 普通全文fact-only | 3/3 | 0/3 | 3 |
| 普通同材料自审 | 3/3 | 0/3 | 3 |
| 教师源证据表指导 | 3/3 | 1/3 | 1 |

这里的通道约定是机制诊断，**不是新增Goal的“零推导字段”门槛**，也不把所有materialized consequence都说成语义错误。三臂原生预测保持Entailment、Entailment、Contradiction，不把标签正确改判0/3。另以独立审核后原值子集执行，三臂都能重算3/3，但这是作者审核的分析控制，不是自动恢复或原始frame通过。

普通自审的请求hash不同、输入2805→6252tokens，但内容逐字与首读一致，不是缓存复用；因此不继续原样或同类提示重试。guided输出3312→1370tokens，少了多项推导状态，但86仍硬断言dependent(Charlie,Bob,2015)，与152(b)(1)的例外冲突；72也仍物化额外适用性状态。教师表能生成不等于执行器已可靠使用。

普通81删除实际151c规则仍Entailment，因为硬注入了查询原子；普通86对Charlie/Bob依赖状态的复查仍Unknown。这些干预只分析原响应，非新母来源或标签。它们说明原生答对可能掩盖后续复用风险，不据此追加所有分支都必须实测的验收。

### 简单控制：利用已有API和引文隔离后重执行

新普通控制不读教师源表或标签，不按这三例写基础谓词白名单。它利用实际自描述API：命名的适用性状态要求原句对应的条款引用，单词状态检查字面状态词，带section根的allowance概念检查原引用；没有凭据的记录隔离，既不改为false，也不填值。现有规则和优先级重新计算后果。

这不是无歧义无损的格式适配，而是一条明确的新部分拒收/重执行路径；原frame和旧结果不变。隔离的20条不都为假，其中包含正确但未经独立断言的推导。它依赖这份API的自描述名称，可错隔离有效同义表达，也可能漏掉同词错角色；6项回归明确保留这些边界，不声称通用NL忠实性证书。

该控制对普通首读、自审、guided三路分别实际重算3/3，新增模型0；86例外后件正确成为Contradiction，81删151c规则后成为Unknown。所有输出来自实际源程序执行、无fallback，保存/加载逐项一致。原源API/规则和旧优先级获取成本对所有臂共同保留，不称完整系统无需教师。

这处理了本次观察到的残余错误，说明源表的局部效果不足以建立超出简单控制的独立机制。它没有证明新例泛化、两项贡献或整体训练就绪。本轮到此不再购买该三例的契约提示，资源并未耗尽。

[完整真实源表/三臂结果/费用](legal_evidence_contract_results.json) · [主审计](audit_legal_evidence_contract.py) · [简单控制实际重执行](legal_evidence_contract_guard_control_results.json) · [控制代码](../../experiments/rr_v2_ordinary_assertion_guard.py) · [冻结库/原值/隔离原因/证明](../../artifacts/rr_method_redesign_20261109/ordinary_assertion_guard_control_v1_20261110/frozen_guarded_execution.json)。

### 问题定位及后续工作

[既有SARA信息抽取研究](https://aclanthology.org/2023.nllp-1.12/)连接案例结构化与符号求解；[Proof-Carrying Legal Reasoning](https://www.mdpi.com/2504-2289/10/9/295)已有事实/规则分离、源链接证明及校验修复；[DDL自动形式化研究](https://arxiv.org/html/2506.08899v1)也讨论跨段原子复用问题。本轮没有将这些共用环节重新命名为两项贡献。

真正尚缺的是在同信息强对照下两项机制的独立作用。本次学习失败既不能归结为截断，也不能证明执行模型普遍无法处理法律输入：已有手工指导和普通隔离路径均正确。问题需从“生成更长指导表”转到**源接口携带哪些可复用的法律作用范围**，并先检查强普通缓存是否已足够。

已只读检查原73/77/83/88及3306原文：3306(a)(1)明确不计相关家政服务，(a)(4)限制家政雇主身份向其他服务复用。下一步检查实际已有表示能否保留付款人、服务和该限定范围，与按子条款拆开的普通源缓存比较。当前项目法条按calendar year，不引入外部现实税法的其他期间；不重开年度cap/付款去重、旧A/B/M1/M2已反证实例，不在有具体机制差异前批量生成。此处是下一项离线科学工作，未宣称新机制成立。

[精确源范围及既有输入检查](../../artifacts/rr_method_redesign_20261109/legal_3306_scope_inspection_v1_20261110/source_scope_and_existing_input.json)。

### 请求、费用与保护

本轮**4E/1T，累计1397E/67T、pending0**；1464calls/224meta/136oracle。前1459/219/136逐行保留，新增5calls/5meta/0oracle，另存SQLite快照。失败源表仍计物理请求；客户端重试0，4E全部OFF/stop/无reasoning，教师可见attempt1/无工具事件。教师供应商内部HTTP重试不可观测，不能把其未知次数记为已证实的0。原服务未改，无生成客户端。

| 实际请求 | 输入 / 输出tokens | 请求耗时 |
|---|---:|---:|
| Qwen初始源契约（拒收） | 2664 / 2675 | 73.806秒 |
| 普通全文事实搜索 | 2805 / 3312 | 91.521秒 |
| 教师固定源段契约 | 20978 / 6223 | 122.565秒 |
| 普通自审 | 6252 / 3312 | 94.839秒 |
| 新源表事实读取 | 8401 / 1370 | 40.513秒 |

4E合计20122/10669tokens、300.680秒；教师2700 reasoning为输出子集，总物理请求耗时423.244秒。源表获取+读取163.078秒，普通首读+自审186.361秒，但教师/执行器资源不同、残余错误不同，不作一般因果成本优势；简单隔离还可复用首读，不需要新表。失败获取与自审成本均不从累计账本中删除。

执行器增量API现金0；教师实际发票、GPU分摊和项目总费用未知，未把未知记零。新母来源/原生评分/oracle/TEST均0，未启动主训练、完整评测矩阵或论文。7项v1契约、9项真实失败修复及6项部分控制回归通过；代码、所有wire、拒收、实际版本、源/运行库和账本差量保留。检查数量不代表贡献验收。

[初始失败](../../artifacts/rr_method_redesign_20261109/legal_evidence_contract_source_v1_20261110/result.json) · [真实教师源表](../../artifacts/rr_method_redesign_20261109/legal_evidence_contract_teacher_v2_20261110/result.json) · [实际guided读取](../../artifacts/rr_method_redesign_20261109/legal_evidence_contract_guided_v2_20261110/result.json) · [真实自审](../../artifacts/rr_method_redesign_20261109/legal_evidence_contract_review_v2_20261110/result.json) · [本轮决定及不同请求核对](../../artifacts/rr_method_redesign_20261109/legal_evidence_contract_audit_v1_20261110/comparison_decision.json)。

---

以下均为历史快照，旧状态/下一步不覆盖当前两份执行文件。

## 历史证据：同初始源普通API控制已接通，核心研究缺口仍是两项独立作用

**本次真实取得了另一套可用法律API和规则，并完成3个既有TRAIN问题的规则执行、语义核查及冻结恢复；强普通控制同样能做到，不能据此宣布两项方法贡献成立。Goal active、未完成。** 最新目标/授权仅见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前缺口和下一项实际工作仅见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。下文旧报告中的未来计划、未测声明及账本数字均是当时快照，不覆盖本节和两份当前文件。

### 同初始法条获取接口：已做的真实控制

原两份标量接口、关系模块12个法律谓词及角色顺序本来就是教师提出的，原schema未枚举这些名称；原提示给定了1个中性名册关系及参与人/跨条款连接指导。此前“接口从零获取未测”的表述过宽：尚缺的是普通缓存从同一初始源自行获取接口并计入获取成本的控制。

本次教师沿用原配置和原151/152全文/局部模块/角色提示，**未给已有API、程序、case/query、原生标签**；普通缓存实际生成15个谓词及14条规则，主体在前、claimant在后，与旧API顺序相反。不是复制候选体。新缓存没见63(c)(5)，不拿原87评它；原四例组与本次三例组分别报告，不混成新的独立样本。

原生成的静态Python程序缺后端different和authority字段，首个空事实smoke报KeyError；只补空附加不等约束后，真实有规则执行又报KeyError authority。这是生成协议没有交代完整后端结构与验证器未检查全部运行字段的实现不兼容，不是新方法优势。新适配器只读取实际静态字面程序，按原引文在原源文中定位trace元数据，并补空附加不等约束列表；规则体、后件、数值、优先级及unresolved逐字语义不变。精确引文不存在或缺实质字段则拒收。原错误、每版适配、程序摘要及冻结源码均保留，**不称原始代码直接通过**。

### 真实事实错误、修复与3例主路径证据

首个执行器批读把规则推导结果当作硬事实：81直接塞入151c适用及扣除资格，86从给定qualifying-child升级为dependent并塞入152b1结论，72给2015错误套151d5、从问题抄$2000。72题目专属引文被既有validator拒绝；81/86即使引文逐字命中原事实，也不等于该原子是合法基础事实。首读的模型语义错误与后端字段异常分开保留，不计成功。

修复使用普通fact-only读取：不给问题/规则体/答案，明确与旧候选共享的基础概念分区，并沿用新API的实际有序角色。给定152(c)(1)资格只读为qualifying_child，原文直接称dependent时才读为dependent；明示151扣除资格读为allowable，不提前推导d2/d5或金额。独立身份、年度日历对齐只来自任务名册，是共享作者任务归一化，不算学习；没有填充生日、金额或法律前提。

| 既有TRAIN来源 | 实际新模型基础事实与规则路径 | 已缓存原生核查 |
|---|---|---|
| 81 | 明示dependent(Bob,Alice,2015)经151c产生查询证明 | Entailment，正确 |
| 86 | 两条qualifying_child经152a连接，再使Bob触发152b1 | Entailment，正确 |
| 72 | 明示allowable(Bob,Alice,2015)及共享年度/身份元数据，d2零金额覆盖一般2000 | Contradiction，正确 |

3/3有实际源规则证明，fallback0，保存/加载重放一致；全部评分复用已打开TRAIN记录，新增原生评分/oracle/母来源均0。81漏了Bob名册，但实际151c证明只依赖正确的明示dependent，不补值、不为非必要字段再发请求；完整名册2/3单列。86沿用首读多绑定Alice的旧查询：只有实际正见证可推出原存在式问题，不能把该单人查询的否定当原问题否定。**3例正确不是整份14规则的NL忠实性证书，也不是新盲测或两项贡献。** 输入概念分区是给定指导，不称自动学得该边界。

### 已完成的实质离线反证：原生答对可掩盖规则绕过

仅重放真实输出，不新增模型/标签；旧坏frame仍拒收，这些干预不是新原生案例或改分。

- 原81删除实际151c适用规则后仍Entailment，因为首读已硬塞查询原子；真实fact-only输出在同一消融下为Unknown，说明它的成功确实依赖规则。
- 原86的例外后件dependent(Charlie,Bob,2015)，首读将其硬设为真；即使接入正确152b1优先级，正负冲突仍Unknown。真实fact-only输出保留qualifying_child前提，经规则得到Contradiction。
- 精确引文能抓72题目金额泄漏，却抓不住81/86把推导结果伪作给定事实。简单“删掉全部规则头谓词”也不够：81显式dependent、72显式扣除资格同时是合法事实和其他规则后件，会被误删。

这些结果将具体法律瓶颈定位到**明示法律状态与可撤销推导状态的证据边界**。普通fact-only提示已解决本次实例，故新方案必须与同信息普通定义查找/事实搜索/纠错缓存比较，不能拿语法校验作弱对照或仅为此加一个gate。下一步先复用实际错误—修复/源规则做离线等价与反证；没有额外作用不批量生成，不追加自动化或零提示验收要求。

[反证脚本](audit_legal_recorded_status_promotions.py) · [完整实际frame/规则干预结果](legal_recorded_status_promotions_results.json)。

### 纠错知识确有复用，但普通控制已覆盖

按同源精确引文及同有符号后件，从实际旧教师复核缓存迁入两条152(b)(1)>152(a)优先边；新API/规则体不变、无模型请求。新程序对86的上述例外后件由Unknown变Contradiction，原3个原生预测不变。是同一政策不同程序间普通纠错模式复用，不是新来源迁移或独立方法贡献。

源步骤新203.180秒、旧133.135秒只是单次观察。虽共享原151/152原文和角色提示，接口形状、修复、读取契约及端到端成本并未完全配对，不据此宣称某架构一般更省或更贵。普通控制真实成功足以约束创新判断，不能把成本因果尚不完整写成对照仍未做。

### 任务口径与实现修正

原87在开放叙述/未知其他人物下仍Unknown；SARA有限原案例人物域Alice/Bob且“另一个”排除Bob时，显式Alice不具资格足以否定63(c)(5)前提。候选与旧独立缓存各自的真实规则均经**已有evaluate_guard**得到原81/86/72/87的4/4跟进重放。原3/4结果保持；加未知Charlie的控制回到Unknown，没把缺失151条件当false。有限人物域是经作者审核的原生任务解释，不冒充自动源文证明或新算法。

此前判断需要新投影实现不准确：代码已有对应函数。本次重复生产模块已撤回，原型与首次报告保留在工件历史；现调用现有函数。确实修复了内核一处错误：决定性负证据本身同时受正证据支持时，旧分支仍可否定查询；现非函数谓词及函数金额的相应反证都要求该见证无相反支持，冲突保持Unknown。26项相关回归及7项字面适配回归通过，不修改冻结历史源码/原模型输出。

OpenExempt共享额度候选也已离线撤回：原EV的精确旧求解函数为每个asset/citation复制原额度状态，考查每资产独立合法替代；两资产800/105、预算700的旧函数重放为700/105，非组合优化的700/0。组合全局分配不是当前原生任务缺口，不将其新增为验收或重跑v6。

[任务作用域与原EV审计](legal_task_scope_results.json) · [接口获取来源审计](../../artifacts/rr_method_redesign_20261109/legal_native_scope_completion_v1_20261110/interface_origin_audit.json) · [26项内核回归](legal_guard_conflict_final_regression.txt) · [7项适配回归](legal_ordinary_literal_regression_v2.txt)。

### 账本、耗时与费用

本次2E/1T，累计**1393E/66T、pending0**，1459calls/219meta/136oracle；前1456/216/136逐行相同，另存SQLite快照。所有请求完成，无重试或教师工具事件；执行器OFF、stop、无reasoning；教师原high、显式温度未设置。原服务身份不变，无生成客户端。

| 实际物理路径 | 输入 / 输出tokens | 请求耗时 |
|---|---:|---:|
| 教师普通API与程序获取 | 16069 / 10745 | 203.180秒 |
| 执行器首次接口事实/查询读取 | 1512 / 1470 | 39.890秒 |
| 执行器fact-only修复 | 903 / 734 | 19.749秒 |

教师6468 reasoning tokens为输出子集；3请求总262.819秒不是工程总耗时。执行器增量API现金0；教师实际发票、GPU分摊、项目总费用未知，不把未知记零。新来源、原生评分、TEST、主训练、完整矩阵及论文均未新增/启动。已封存每次实际版本、原始wire、拒收、规则证明、冻结库、修复前后与账本差量。

[完整控制/证明/请求费用审计](legal_auto_interface_results.json) · [可重放审计脚本](audit_legal_auto_interface.py) · [实际教师输出](../../artifacts/rr_method_redesign_20261109/legal_auto_interface_cache_v1_20261110/source.json) · [首读原始拒收](../../artifacts/rr_method_redesign_20261109/legal_auto_interface_reader_v2_20261110/execution_closed_before_grading.json) · [真实修复输出](../../artifacts/rr_method_redesign_20261109/legal_auto_interface_fact_search_v1_20261110/execution_closed_before_grading.json) · [实际冻结库](../../artifacts/rr_method_redesign_20261109/legal_auto_interface_audit_v1_20261110/frozen_library_and_cases.json)。

---

以下保留各次原始结论与当时下一步，均为历史参考。它们不覆盖当前两份执行文件，也不恢复旧模型额度、修复轮次或被反证的研究方向。

## 历史证据：真实源反馈已接通，但直接普通程序取得同等正确性且更省

**本次完成真实反馈获取、技能更新及冻结恢复，没有停在设计卡。普通强对照吸收了拟议作用，当前两项独立贡献仍未成立，Goal active。** 不扩大年度单组件小试或建库，执行边界仍只由[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)维护，下一项工作见[当前证据页](../../docs/METHOD_REDESIGN_CURRENT.md)。

### 实际生成与更新

复用原TRAIN88的3306(b)(1)源片段，模型不见原生case/query/标签、付款标注、旧正确期望或正确程序。已有8个输入池曾由作者设计，阈值7000在共同候选合同中给定，故不称完全自主反例生成或从零发现阈值。两个提示在首次调用前共同封存，先运行普通自由源测试生成，再运行固定输入判值。

固定输入只按候选预测的分区和不可区分组选择，不读取源参考答案。普通对照见同一源、候选族和全部未标注池，可选择或创建更强输入，提示明确要求前/后条件、边界、交互和变异辨别。两臂同原教师high配置，均实际给出四个正确金额和有效源引用，都从52个候选类唯一识别payer/payee/payment_year内年度cap。引用命中单独检查，不当语义证明；独立源参考只在保存响应后评分。

普通自由生成还自行构造了3000+4000+1跨服务的阈值测试，以及分别改变付款人、收款人和年度的四行测试。不是复制作者8个正确期望，也没有把构造探针当新增原生样本。

两路反馈分别进入普通精确一致性学习器，新plan替代旧模型include_all。旧6/8输出保持不动，新库均过8/8源检查，实际标注输入局部20597，保存/加载后重放相同。阈值、候选语法和公共付款准入给定，学得的是scope keys及操作；不宣称所有工资/雇主前提已学或新增原生成功。

### 强成本对照改变了后续决定

| 实际同教师路径 | 本次源语义结果 | 输入 / 输出tokens | 请求耗时 |
|---|---|---:|---:|
| 普通规格驱动自由测试生成 | 4/4反馈正确，唯一识别，更新后8/8 | 14590 / 2154 | 47.629秒 |
| 固定分歧输入判值 | 4/4反馈正确，唯一识别，更新后8/8 | 15156 / 652 | 20.051秒 |
| 直接普通Python政策程序 | 一次获取8/8，局部20597及冻结恢复一致 | 14913 / 195 | 11.331秒 |

第三臂使用同教师、同源/关系/候选族/未标注池，允许公共运行器支持的helper/lambda；没有看两份新反馈、正确程序或原生标签。它直接学得按三键分组并封顶的普通代码。固定判值比自由测试短，但直接程序在本次正确性相同且更省，不能只选前两臂宣称成本优势。单次配对也不推广为稳定时间排序。

普通有限版本空间选择可完全复现固定输入选择，故选题本身没有独立算法差异。源反馈的获取可行性已证实，但“范围反例＋一致性更新”当前没有超出强对照的独立能力或成本作用。年度同例不再追加模型请求，普通直接程序作为可复用基础保留。

### 去重后的可识别性口径

此前128/104分别是语法表示及匹配局部20597的表示数，不能当相互独立的法律解释数。唯一payment_id使包含它的scope等价；include_all也与scope无关。按这些恒等式归并后为52个候选语义类，其中28个匹配原局部20597；源检查仍唯一识别，池内最少4项足够。旧枚举工件保留，本次另存归并与核验，不改写原结果。

### 相关工作与证据边界

[软件工程法条分析](https://law.mit.edu/pub/aidrivenstatutoryreasoning/release/1)已有覆盖/变异驱动的法条反事实；[SpecSyn](https://arxiv.org/html/2604.21570v2)已有变体判别引导规格细化；[规格驱动测试生成](https://research.google/pubs/grounding-ai-agents-in-contracts-an-empirical-evaluation-of-spec-driven-test-generation/)已有先解释规格再构造测试。当前小试检验的是它们作为强普通控制后的实际差异，不将通用测试/筛选单独算新贡献。

下一项仍围绕法律数值作用范围，先只读核对既有OpenExempt输入中单项上限、共享总额及未用额度转移的跨条款联系，复用已有正确性组件和v6强对照；先检查是否已有等价处理，不重跑旧研究或把优化器换法律名称。没有新独立差异前不批量生成。

### 账本与费用

本轮0E/3T，累计1391E/65T、pending0；3次均attempt1、无工具事件，教师原high/显式温度未设置，执行器保持OFF且未调用。总44659输入/3001输出tokens、79.011秒，其中reasoning1583是输出子集。旧1453calls、214meta、136oracle逐行保留，新增3calls、2meta、0oracle，当前1456/216/136，SQLite另存备份。教师实际发票及项目总费用未知，没有把未知记零。母来源、原生评分及TEST标签新增0；未启动主训练、完整矩阵或论文。

[逐臂结果/成本/账本](legal_feedback_acquisition_results.json) · [实际更新审计](audit_legal_feedback_acquisition.py) · [真实自由反馈](../../artifacts/rr_method_redesign_20261109/legal_feedback_acquisition_v1_20261110/free.json) · [真实固定输入反馈](../../artifacts/rr_method_redesign_20261109/legal_feedback_acquisition_v1_20261110/fixed.json) · [同教师直接程序](../../artifacts/rr_method_redesign_20261109/legal_feedback_direct_control_v1_20261110/source.json) · [三路冻结库](../../artifacts/rr_method_redesign_20261109/legal_feedback_update_v1_20261110) · [4项回归](legal_feedback_acquisition_regression.txt)。


## 前次证据：年度上限由普通程序真实学得，两项独立贡献未成立

目标、验收和授权只维护在[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，最新证据与实际工作只维护在[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。本报告及各协议是证据/历史快照，不恢复旧调用或修复轮次限制。Goal active、未完成。

**实际进展是普通Python/PAL路径学对了3306(b)(1)的年度金额作用范围，并完成保存/加载和标注输入的局部执行。自定义计划未显示额外作用，不能把同一程序或普通去重包装为两项贡献。** 最近新增7E/0T，累计1391E/62T、pending0；1个新TRAIN事实标注视图、0个新原生任务评分。

### TRAIN88的额外标注与公共文本分开

只打开原固定TRAIN88对应参考case，白名单输出payment/service、参与人、用途、时间、金额等事实，不输出goal/答案/directive，不打开其他case或TEST。新增oracle记账。公共文本给服务期间；参考事实另把三笔农业付款的payment start标为2017-09-02，反向付款标为2018-09-02。**这些是额外TRAIN标注，不是从公共文本无歧义恢复出的付款日，也未补进旧模型frame。** 参考事实没有means_；现金及地点的缺省来自官方任务程序，不伪称明示事实。

局部年度上限输入为已准入的唯一物理付款，其他3306工资排除/雇主适用条件在组件外。农业服务有三名employee见证，同一付款可产生多个见证；共同adapter按payment身份只计一次，向所有臂开放，不称学得第二机制。三笔不同收款人金额6771、6954、6872，局部总额20597。该结果不是完整3306(a)(2)(A)预测或新原生评分。

### 有限真实生成、执行与具体修复

| 路径 | 实际输出与源检查 | 判断 |
|---|---|---|
| V1普通SQL | 整笔排除、按payment_id聚合，4/8源检查；多见证还能错误放大HAVING金额 | 真实模型语义错误，原代码保留 |
| V1计划 | 年度keys与逐笔cap冲突，引用不是原文；严格拒收 | 原始值另作诊断6/8，不接收入库 |
| V2 SQL反馈 | 看见两份旧错和8项共同源反例，仍返回逐字同一SQL，4/8 | 请求不同且非缓存命中，不再原样追加 |
| V3 SQL/计划 | 去除错误代码锚定、共享准入、操作定义及8项反馈；SQL为非法嵌套窗口聚合0/8，计划include_all为6/8 | 不因SQL较弱就宣称计划有优势 |
| 普通Python/PAL | 首响应采用lambda/helper，旧one-def运行器拒收；扩展必要声明后，真实执行发现helper返回dict、外层迭代keys触发TypeError | 区分接口实现问题与模型代码错误，不把首响应改判成功 |
| 普通Python执行反馈修复 | 9项运行器离线回归先过；query格式明确为已注册字符串；给同一源/共同反例及实际TypeError，模型自行将helper改为return groups.values() | 8/8源契约通过；按payer/payee/payment_year累计、各组min7000再求和。实际代码冻结/加载后重放局部20597 |

普通Python成功依赖实际新模型修复，不是人工把软件fixture当模型产物。运行器保留资源限制及危险调用拒绝，不转换源数值或规则。SQL/计划/Python后期均见同一源反例反馈，故不是纯原文盲编译；它们都没见原生case/query/标签或标注运行记录。8条检查是源语义软件探针，不是8个新原生来源，也非完整自然语言忠实性证书。

源3306(b)(1)按同雇主/个人/年累计封顶；官方局部实现按单笔min7000，在允许同年同人多付款的本组件输入合同下有反例。**不据此断言原数据标签错误**：原题可能以年汇总行表示付款，原88三名收款人各未超上限。比较差异和适用输入合同均保存。

### 单点正确不能辨认法律作用范围

离线穷举5个字段的32种scope子集、4种金额操作，阈值固定7000，共128候选。**104个得到原88同一局部20597，仅1个通过全部8条源契约检查。** 在这个有限语法和检查池内，4项即唯一识别：不同付款人、不同收款人、不同付款年、同年度键但不同服务。枚举得出的最少4项不推广为一般最优查询定理。原年度同人双付款检查在这组最小池中冗余，审计不预设应当需要5项。

普通精确一致性筛选也恢复同一plan，因此这确立了“单点监督可能掩盖错误范围”的问题，尚未建立新学习算法的增量。现已打通普通程序主路径；下一步按当前证据页核对既有TRAIN中的复用边界，不继续年度同例接口扫描，不扩大完整建库。

### 既有Airline输入的离线边界

未调用模型或打开标签，复用原TRAIN第一条Phoenix→Rio de Janeiro的Basic Economy行李输入。符合随身携带尺寸的第一件不计托运，其余四件在已正确映射基础费/尺寸费/重量费的局部合同下，逐件`base+max(size,weight)`相加为870；错误的先汇总再max为800，错误全加为990。实际输入已触发区别，不需要构造新母来源。金额映射是显式作者源参考，不是模型读取/学得政策，不含票价或新原生预测。普通正确缓存也能表达正确公式。

这与年度分组一起支持作用范围问题的真实任务必要性，未建立新机制优势。下一个实际问题是怎样从原法条自主获得有辨别力的源反馈，以及相对普通反例生成的作用；8项作者检查不能当已学能力。原Airline原始语料无native split，本项目既定TRAIN归属保留，没有把unsplit改称原生train。

[离线审计入口](audit_existing_airline_scope.py) · [原输入、逐件金额及错误范围比较](../../artifacts/rr_method_redesign_20261109/existing_airline_scope_v1_20261110/local_scope_comparison.json)。

### 费用、版本与账本

7次执行器共8000输入/656输出tokens、18.624秒，均stop、thinking OFF、无reasoning/截断，客户端重试0；新增教师0。已知executor增量API现金0，GPU分摊、历史教师发票及项目总费用未知。旧1446条calls、208条meta、135条oracle逐行保留，当前1453/214/136；SQLite另存快照。所有坏输出、V1/V2/V3源码与manifest保留，失败不删账。不启动主训练、完整评测矩阵、TEST或论文。

[逐请求结果与费用](legal_annual_scope_results.json) · [可重复审计](audit_legal_annual_scope.py) · [TRAIN事实边界审计](audit_TRAIN88_reference_facts.py) · [实际标注执行/冻结库/128候选](../../artifacts/rr_method_redesign_20261109/legal_annual_scope_execution_v1_20261110) · [实际模型修复程序](../../artifacts/rr_method_redesign_20261109/legal_annual_python_repair_v1_20261110/source.json) · [9项运行器回归](legal_ordinary_python_regression.txt)。


**前次阶段结论：新增的普通程序缓存独立获取/源复核后，在共享已学API和公共求解器下复现81/86/72正确、87未决，与候选逐例相同。两项独立贡献尚未成立。** 原协议另一组18/8/85/76仍4/4，未重跑。当前角色/优先执行实例不扩大，API从零获取及端到端成本未验收。原Goal active、未完成，不启动完整训练。

最新用户定位已执行：允许复用成熟语义解析、关系连接和非单调推理；不因底层算法已有就否定法律方案。保留旧A/B和旧M1/M2负结果，它们的标签通道并未换法律名称重新启用。本轮处理不同对象：原文中的跨条款关系调用，以及适用条件与法律效果。五库/原128 TRAIN划分不变，法律承担主要验证，Airline/ProofWriter后续承担迁移与边界，不新增五库全胜要求。



## 前次真实执行：源152(c)(1)程序、字段错误及部分证据证明

累计**1384E/62T、pending0、135个oracle视图**，本轮5E/0T、1个新TRAIN原文评分。已完成原13条件/事实对齐和实际源程序执行，不是只有诊断文档。**新增1个真实Qwen源程序、1个原生TRAIN来源闭环；直接对照和普通部分绑定缓存也正确，所以两项独立贡献仍未成立。** 原A/B、旧M1/M2和旧0/89记录保持原样，不用这次普通标量程序改写旧实验。

### 真实生成、失败与接口对照

Qwen只见原152(c)法条和公共六输入原语契约，没有case/query/标签，一次返回完整普通Python布尔函数。现有纯AST内联编译通过，四条件的全域SMT参考比较通过；程序使用`same_abode_days <= tax_year_days // 2`拒绝不满足严格过半的情况、严格年龄<25，四合取条件均保留。API由研究者提供，不算从零学得接口；审计参考来自法条转写，不是原生答案。模型代码未直接exec。

| 事实读取 | 实际结果 | 判定 |
|---|---|---|
| guided首读 | 关系字段将Bob置taxpayer、Alice置individual；把同住起始日2015-09-01当Bob出生日期，引用却是无日期“有一个儿子”句 | 形状正确、语义拒收，完整原响应保留 |
| guided普通反馈 | 明确individual是关系承担者、taxpayer是其关系所指对象，并给原错误和源诊断 | 仍逐值返回同一错误，不是缓存命中；停止同方式重试 |
| 同提示unguided | 与guided反馈消息、模型和采样完全相同，仅移除response_format | 角色修正，出生日期仍虚构；整体仍拒收，不能把全部错误归因guided |

三次的同住事件本身都正确：Alice/Bob，2015-09-01至2019-02-03；与独立的152(c)(2)关系2015—2020期间没有混用。出生日期跨句借用是实际模型错误，首版角色定义不足还含接口提示问题。原源程序无截断、类型或执行缺陷。

### 整帧拒收的实现修复与实际证明

本轮原型最初要求整个frame无误才执行，过度排除了与结论无关的字段错误。新增公共[部分标量证据组件](../../legal_skill_guard/rr/partial_scalar_evidence.py)，只将**独立核实且来自原模型字段的值**放入求解器，错误或缺失字段保持未知。原frame不改，不用确定性解析器替换错误值，不补生日或申报。法条正确性和实际使用证据的检查均未放宽。

三个真实frame均各自提供正确同住字段。查询年份2019、共享日历365天，原模型所报同住区间裁切为34天；源程序对任意年龄、相对年龄、申报状态以及关系布尔值都返回false。最小充分证据只含34天与365天，分别移去任一值都会恢复真假两种可能。六项回归验证了未知保留、隔离值不入约束、缺失关键证据不强答、类型错误及不一致域拒收。程序与库冻结/加载后重放一致。

该证明以原生任务完整事件记录的归一化为条件；不假定记录完整的纯叙述视图仍unknown，不能把已报告34天无条件当所有可能同住天数的上界。官方152(c)(3)有相对年龄的亲子缺省分支，但仍另外检查绝对年龄，不是“无生日就整个年龄条件成立”；这些缺省没有进入学得源程序。

原生预测及直接模型结果均先封存，再开原13TRAIN标签，二者均Contradiction、正确。三个读取视图属于**同一个来源**，不是3个新原生成功。部分证明没有调用回退答案；另建的窄确定性reader替代对照也得到正确结果，但该条明确标为reader fallback/control，不计核心学习成功。该解析器可校验原模型字段与原句的关系，不能把其值偷偷填进模型frame。

**这次补齐的是普通源程序/真实有效证据的执行链，以及过严校验的工程修复。** 普通部分绑定缓存同样可用公共SMT组件，直接模型也给出相同的34/365天依据。因此不将字段隔离、SMT删证据或这一个成功样例包装成两项新贡献，不扩大这一实例的建库或同例生成。

### 费用与保存

五次执行器请求共4207输入/904输出token、24.577秒，均stop、thinking OFF、无reasoning内容、重试0；教师新增0。executor增量API现金0，GPU分摊、历史教师发票和项目总费用未知。原1441笔calls、204条meta、134条oracle逐行保持，仅新增5calls、4meta及原13原文评分1视图；当前1446/208/135，SQLite另存备份。全部失败、源版本、原始wire、冻结manifest、评分顺序和对照均保留。没有TEST标签、主训练、完整矩阵或论文。

[完整逐例/调用/费用审计](legal_temporal13_results.json) · [可重复审计](audit_legal_temporal13.py) · [实际源程序与首次失败](../../artifacts/rr_method_redesign_20261109/legal_temporal13_v1_20261110) · [普通反馈失败](../../artifacts/rr_method_redesign_20261109/legal_temporal13_v2_20261110) · [同提示unguided](../../artifacts/rr_method_redesign_20261109/legal_temporal13_unguided_v1_20261110) · [部分模型证据执行、原始账本增量及TRAIN评分](../../artifacts/rr_method_redesign_20261109/legal_partial_temporal13_v1_20261110) · [6项回归](legal_partial_evidence_regression.txt)。


## 前次有限验证：普通事实检索已处理原13/81边界

本报告保存研究证据。所有旧段落中的“下一步”、调用/修复限制和阶段停止决定仅是历史记录；当前执行条件与下一项工作只维护在[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)和[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)，不由本报告另设。

累计**1379E/62T、pending0**，本次2E/0T、0新oracle。不是停在文献总结：已用原Qwen3-8B、thinking OFF运行两次普通事实检索，原TRAIN13返回`No applicable fact`，原81逐字返回“Bob counts as Alice's dependent under section 152(c)(1) for 2015.”。两次均stop，无reasoning输出、重试或截断。合计1120输入/28输出token、0.890秒。格式示范仅取原TRAIN8/18，含负例；给普通对照API释义，明确单个152(c)(2)关系不等于复合资格，不能将该释义算新的学习。

这组结果没有观察到拟议的“把待推导资格塞成事实”错误，故不新增专用门控、不追加同目的生成。它只验证事实搜索边界，不是原生13题答案、完整SymBa复现或新方法成功。

[SymBa论文](https://aclanthology.org/2025.naacl-long.124/)及[官方原校验器](https://github.com/lbox-kr/symba/blob/df0e291152093e1d8a56a545b9310bd502f8dcd0/hiereason/symba/validate_statements.py)已核对。固定原代码与clingo5.6.2实测：角色不合一会拒绝；人为构造的“谓词匹配但NL描述不足”记录会通过。这是离线覆盖检查，不能冒充真实模型错误。普通负例提示已经处理本次真实边界，也不能据构造反例宣称胜过SymBa。只读取外部源码文件，未下载其数据/测试提示或整仓进行全面复现。

### 原任务语义与未决的解释

[SARA官方定义](https://nlp.jhu.edu/law/sara_v2/)使用二值truth；官方法条程序有失败否定。我们局部signed-Horn模块的Unknown是当前程序覆盖边界，不证明原生题本身无解，也不向原Goal增加全局开放世界要求。反过来，缺规则/缺事实或模型失败也不能直接改为False。原87未决及3/4历史成绩保留，不以强行闭世界补答计核心通过。

只读官方源文件63/152/3306后，原88的支付年仍未补齐：3306明确查询`start_(Remuneration,Time)`，没有把服务期间当支付日期的源约定。原20597是条件合计，不是新取得原生3306(a)(2)(A)成功。官方源注释提及quarter，而实际源程序及本项目公共简化题面用year，不把注释追加成新条件。没有读取参考case、原生13标签、DEV/TEST标签或改原输出。

六项离线断言通过后才发送真实请求。原1439笔calls、203条meta及134条oracle与上次备份逐行相等；当前增加两条calls、一条实验策略meta。新SQLite备份已保存，账本不重置。executor增量API现金0，GPU分摊及总项目费用未知；教师本次0，旧费用全部保留。两项贡献仍未成立，不扩大当前假设的批量实验、不标记Goal完成。

[可重复审计/费用/逐例结果](legal_fact_boundary_results.json) · [审计入口](audit_legal_fact_boundary.py) · [原始两次响应及wire](../../artifacts/rr_method_redesign_20261109/legal_fact_boundary_v1_20261110) · [原任务源语义核对](legal_task_semantics_audit.json) · [源语义复现](audit_legal_task_semantics.py)。


## 前次证据：独立普通程序缓存的真实获取与源复核

最新累计**1377E/62T、pending0**；本轮0E/2T，oracle仍134。原1437笔模型计账、201条meta、134次oracle逐行保留。原目标/边界只维护在[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前证据/下一步只维护在[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。以下协议是实验快照，不恢复旧调用或修复轮次限制。

这次对照补的是**规则体的独立获取**，与旧同程序副本不同。普通Python缓存只看原151/152源文、63(c)(5)段和共享的已学输入/输出签名，不看候选规则体、优先边、原case/query或答案。可用普通集合代码，也可调用同一公共支持模型求解器，避免强制重实现基础推理。模型自主选择后者。源请求与复核均未发生工具读取，不借服务器其他文件取得答案。

信息边界必须分清：这是给定已学API的条件对照，未测试从零发现API。对照额外得到63(c)(5)段，原候选则由已学151条件做源匹配转移，因此本次不是初始提示完全一致的架构因果实验。原API/事实获取费用继续保留，不将它们当免费，也不凭本次总耗时宣布获取成本胜负。

| 原四例 | 独立缓存实际主路径 | 已有TRAIN评分与候选 |
|---|---|---|
| 81 | 源152(a)到151(c)真实派生，Alice为claimant、Bob为subject、2015年 | Entailment，正确；与候选相同 |
| 86 | 用Bob作为Alice的dependent得到152(b)(1)适用，并阻止Bob再拥有自己的dependent | Entailment，正确；与候选相同 |
| 72 | 同一Bob/2015键的151(d)(2)置零压制2000通用金额 | Contradiction，正确；与候选相同 |
| 87 | 一个明确负扣除见证不否定所有未问claimant的存在投影 | 未决；与候选相同，不用默认答案补齐 |

独立缓存核心回答3/4、原生正确3/4、未决1/4；实际fallback调用0，未拿fallback正确替代核心。所有输出先封存，再复用既有四例评分，未新开标签或oracle视图；这些是已观察TRAIN诊断，不称新盲确认。另一组四目标18/8/85/76保持原4/4，不与本组拼接重写历史。

### 修复前后证据及检查解释

第一次源生成的Python函数完整，但其公共求解器参数有18处引用失败：空guard_quote、格式/大小写改写和拼接/转述的quote。首次提示对实际引文契约解释不够明确，这部分含接口提示问题，不据此宣称方法优于普通代码。原执行在校验层拒收。静态字面量检查还证实152(b)(1)仅有适用marker，没有消费marker的规则、负规则头或非金额优先边，因而缺了法律效果；这部分是实质源编译遗漏。

保留首响应及绑定源码后，只针对这些诊断做一次源复核，不给原生个案或标签，不给候选规则。教师自己返回11项规则替换、3项新增效果规则及6条优先边。AST应用器只替换模型明确给出的规则/优先字面量，签名、未决列表和代码执行骨架保持。原规则/引文检查不放宽，复核后源字段和原生执行均通过。

软件源检查最初报7/8；剩余项来自检查期望错误，并非模型错误。“qualifying_child(P,Q)”可推出Q是P的dependent，而152(b)(1)禁止Q有自己的dependent，包括P。该原测试要求角色反转问题一定unknown，错误排除了有源证明的Contradiction。原代码、预测、失败记录不改，保存包含实际三步证明的期望校正，允许unknown或源支持的Contradiction；其他七项预期不变，校正后8/8。没有通过修改模型答案或删除源检查制造通过。

实际新产物是独立获取的规则程序与修复、源语义边界检查、四例真实执行和费用账本。运行器/AST应用器8项回归通过。两次教师共37437输入/11634输出tokens、223.210秒；reasoning5914为输出子集。配置重试0，两次不同请求各执行一次，先前费用继续累计。executor增量API现金0；教师实际发票、GPU分摊和总项目金额未知。

**研究决定：共享API后的具名连接与显式例外，在本组不能独占为两项独立贡献。** 普通代码＋源复核已经在新规则体中复现这些行为；这不是用相同程序的副本作否决。API学习仍需单独检验，不能扩大结论为“所有法律源学习无价值”。该轮提出的原TRAIN13事实边界假设已在本报告顶部用真实普通FactSearch检验，未观察到拟议错误；未进行原生13题预测或标签评分。

按需获取本身已有SymBa覆盖；后续原校验器复现和两次事实搜索结果见顶部，不把普通符号回溯换法律名字。

[独立源请求与原代码](../../artifacts/rr_method_redesign_20261109/legal_independent_cache_v1_20261110/source.json) · [首次失败路径](legal_independent_cache_first_failure.json) · [源复核及模型补丁](../../artifacts/rr_method_redesign_20261109/legal_independent_cache_review_v1_20261110/review.json) · [实际复核代码](../../artifacts/rr_method_redesign_20261109/legal_independent_cache_review_v1_20261110/reviewed_cache.py) · [预测封存](../../artifacts/rr_method_redesign_20261109/legal_independent_cache_review_v1_20261110/execution_closed_before_grading.json) · [源证明支持的期望修正](../../artifacts/rr_method_redesign_20261109/legal_independent_cache_review_v1_20261110/source_check_interpretation_correction.json) · [结果/评分/费用/账本](legal_independent_cache_results.json) · [可重复审计](audit_legal_independent_cache.py) · [8项回归](legal_cache_review_regression.txt)。

## 前次证据：原TRAIN18闭环、原协议四目标及独立对照边界

累计仍**1377E/60T计账、pending0**。本轮新增模型0；原1437次模型计账、201条meta及133次oracle逐行保留，只增加原TRAIN18的原文标签视图，oracle134。原服务身份不变，无研究客户端，不启动完整建库、主训练、完整矩阵、TEST或论文。

原TRAIN18事实明确给2015年收入276932、68(b)金额250000、Alice未婚；早期`module_pilot_analysis.json`已经保存这一绑定，故未重买抽取。该记录与后来用275000展示floor+1错误的整倍数软件反例不同。官方**源法条实现**151(d)(3)(B)以`gross_income(Taxp,Taxy,Agi)`供应Agi，本次只核对这项SARA输入约定，不读取官方case/标签或把它当现实税法中的通用等同。原源角色模块先前仅将`true`改为`True`，表达式及输入不改；本轮实际保存加载后执行，百分比22、原query预测Entailment；先封存再读TRAIN标签，正确。

因此原事前协议的四目标18/8/85/76现在4/4，fallback0/4。它们检验151局部百分比、63局部替换值、63(c)(6)(A)条件和68(f)启动条件；不覆盖整套税法、所有源分支或原DEV，不用它们替换另一组81/86/72/87的3/4。18的事实绑定是共享确定性适配，不伪称新Qwen读者或新Qwen源程序生成成功。旧151教师获取14743输入/1610输出tokens、43.269秒（reasoning1034为输出子集）持续计账；本轮新增模型费用0，历史GPU和教师实际发票未知。

### 对照的实际含义

原`legal_shared_cost_comparison.json`早已标注，同库缓存路径与候选复制相同程序/输入/算法，**不是独立获取对照**。这证明共同确定性执行可以省掉一次直接判断请求，不能单独证明法律接口自动获取毫无价值，也不能独占该共同节省。当前法律候选应保持“独立获取/学习策略及端到端成本尚未验证”，不能将复制执行的相等直接升级为整条法律路线被否定。此校正不影响旧A/B算法等价、M1成对监督被普通树吸收和M2同原语简单对照的真实负结果。

新增查新对下一步有约束：[DACL](https://arxiv.org/html/2605.02472v1)已有一次法律编译、类型图、重复执行和最终专家复核；[Proof-Carrying Legal Reasoning](https://www.mdpi.com/2504-2289/10/9/295)已有源链接规则、显式优先关系、确定性证明和针对性修复；[SpecSyn](https://arxiv.org/abs/2604.21570)已有用非等价程序变异和判别检验规范强度。已有算法可复用，但“再存程序/加优先图/做变异测试”不能直接作为我们的独立差异。当前要解决的仍是参与人、作用范围或例外被错译后持续复用的问题，独立的学习/更新机制及其公平比较尚未实现验收。

本轮另只读原DEV的2(b)(1)(A)公共事实，以核对冻结151库是否有实际调用机会。该原例给住房成本40%，存在无需151分支即可决定相关条件的依据；没有把“源中含151引用”当已触发真实复用。未生成、未评分、未开DEV标签或回灌TRAIN；不购买不触发目标机制的演示，也不据这一例推断其他DEV无用。下一项是先具体确定独立获取/复用机制相对一次编译缓存的差异，用已有真实错误离线证伪；不继续为已完成四目标或已知min裁剪重买响应。Goal保持active、未完成。

[原预测、绑定与源检查封存](../../artifacts/rr_method_redesign_20261109/legal_percentage_reuse_v1_20261110/execution_closed_before_grading.json) · [随后TRAIN评分](../../artifacts/rr_method_redesign_20261109/legal_percentage_reuse_v1_20261110/TRAIN_grade.json) · [四目标结果/成本及账本保留](legal_percentage_reuse_results.json) · [可执行复用入口](execute_legal_percentage_reuse.py) · [原同库成本比较](legal_shared_cost_comparison.json)。

## 前次证据：原TRAIN8非循环前提、旧模块实际组合与原TRAIN76

最新累计**1377E/60T计账、pending0**。本次新增1E/1T；18项相关回归通过，所有前次1435笔模型记录、meta及131次oracle逐行保留。执行条件唯一见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，证据/缺口/下一项工作只在[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)原位维护。下文旧方案、协议和数值均是对应实验的历史证据，不是新的调用/轮次限制或执行队列。

本次只补早已固定的TRAIN8、76，未因成功追加来源。教师一次只见原§63/§68源文、共享三原语API和局部模块目标，不见case/query/标签，生成两条婚姻—分别申报—本人或配偶逐项扣除的Horn规则，以及`(year > 2017) and (year < 2026)`的68(f)局部启动函数。三原语及其角色由本次公共接口提供，不称从零学得角色API。原未解决的7703外部关系保留；这次正证明使用case显式婚姻前提，不将整个7703编译算作已完成。

执行模型随后只见原TRAIN8事实、字面年份、同一前提API及原句选项，不见法律条款、法律query或目标适用谓词。实际返回Alice/Bob双向婚姻、双方分别申报、Bob有4324逐项扣除五条事实。独立字面依据检查核对参与人、年份、极性和原句；不补模型漏掉的前提，不从缺失推false。原事实的“allowed an itemized deduction”按共享API作为给定逐项扣除状态；不新增原题未要求的选择行为门槛。

| 原计划原生目标 | 真实主路径与语义检查 | 评分/对照 |
|---|---|---|
| TRAIN8：63(c)(6)(A)是否适用于Alice/2017 | 实际join Alice↔Bob、Alice分别申报、Bob逐项扣除，导出适用；目标Boolean未作为前提 | 预测封存后原TRAIN标签为Entailment，正确；普通正确连接控制相同 |
| 同次实际模块复用，不另计样本 | 源guard逐字匹配旧basic63输入，将上述正证明传入；其他输入未知，旧程序实际证明扣除额0 | 冻结/加载后重现；不是新增原生题或独立贡献 |
| TRAIN76：68(f)是否适用于2018 | 使用原query字面year执行源生成日期条件；局部例外启动为True，不误写整个68适用或扣除额 | 封存后原TRAIN标签为Entailment，正确；正确日期缓存相同 |

上述两例单独2/2，fallback0/2；不把原四例3/4改为整体通过，不声称已完成DEV、未见政策泛化或两项机制的独立作用。实际保存恢复一致、16个正见证边界软件控制、全整数日期比较和源后置条件检查均保留；软件控制不计原生样本。

首次离线fixture漏了case必需的`unresolved=[]`，测试失败后错误地提前发出教师请求，原失败日志、原seal和绑定源码全部保留。教师提示本身不含该fixture，源程序不因此改判模型失败。修复fixture后，68(f)响应的后置条件仍因现解析器只接受input-condition/result-assertion而拒收。按`C⇒A ≡ True⇒(¬C∨A)`确定性重定向，并验证所有input/result的等价及原条件在原程序中可达；没有改变表达式、签名、域、引文或未解决项，没有教师重发。v1的两个原拒收与v2接纳分开保存。

费用：教师输入16126/输出2279tokens、50.292秒；其中reasoning1552是输出子集。执行器输入422/输出255tokens、6.824秒、stop、thinking OFF，客户端无重试。教师旧§63获取成本继续保留，不能将旧函数或输入契约视作免费。已知增量executor API现金0美元；GPU及教师发票未知，总费用未知。131→133次oracle，只在预测封存后开启原TRAIN标签。原服务PID/启动身份不变，无研究客户端或pending请求。

**决定：必要的非循环输入链已经打通；普通正确缓存仍吸收此次作用，不将这项工程修复晋升贡献。** 原计划TRAIN18还需从软件22反例区分出其真实276932/250000输入链；新的学习机制与必要DEV/迁移证据仍缺，不以补链代替贡献设计，不扩完整建库。

[原源响应及拒收](../../artifacts/rr_method_redesign_20261109/legal_primitive_chain_v1_20261110/source.json) · [原响应恢复](../../artifacts/rr_method_redesign_20261109/legal_primitive_chain_v2_20261110/source_recovery.json) · [实际事实响应](../../artifacts/rr_method_redesign_20261109/legal_primitive_chain_v2_20261110/facts.json) · [封存执行及证明](../../artifacts/rr_method_redesign_20261109/legal_primitive_chain_v2_20261110/execution_closed_before_grading.json) · [随后两例评分](../../artifacts/rr_method_redesign_20261109/legal_primitive_chain_v2_20261110/TRAIN_grades.json) · [完整结果/费用/保存](legal_primitive_chain_results.json) · [只读核验](audit_legal_primitive_chain.py) · [18项回归](legal_primitive_chain_regression.txt)。

## 前次证据：旧程序无歧义恢复、原TRAIN85实际执行与普通Python控制

该次累计**1376E/59T计账、pending0**。该次1E/0T，一次原TRAIN85标签视图；原1434笔模型计账及全部既有meta/oracle逻辑快照完整保留。下文旧时点数值保持历史，不作恢复指令。

### 已有源程序可以恢复，不应为这个字段重买模型响应

原教师§63基本标准扣除函数完整，但`domain`是明确自然语言，原解析器要求Boolean表达式而拒绝。其“收入整数、其他输入Boolean”已经由原签名编码；剩余明确语句“head-of-household不能与joint/surviving-spouse并真”规范为`not(H and(J or S))`。本次只改变这个表示字段，原表达式、九个输入、七项义务、引用、未解决依赖及原始拒收JSON逐字不改；没有添加非负收入或默认false。七项原义务均可达且验证，旧函数同时已经正确把新基数传播为联合申报的24000，不需要重写数值框架。

这次恢复单独保存为新缓存，不将原拒收改写成当时成功。原协议早已列入TRAIN85，且其完整§63与源获取TRAIN8完全相同。其query具体指向63(c)(7)(ii)。执行器从旧教师AST中确实存在、语义唯一的替换子表达式及原源引文形成局部参数视图；存在投影检查确认未用输入域可消去，未知法律分类没有被置假。条件未知仍未知，条款不适用时不拿普通3000充当该条款的结果。保存/加载后实际执行相同。

| 已固定原生目标 | 实际执行 | 后封存评分及对照 |
|---|---|---|
| 原TRAIN85：2019年、63(c)(7)(ii)、声称基本扣除3000 | 局部替换金额12000；预测Contradiction；不使用fallback；新增模型请求0 | 预测先封存，再开启一次原TRAIN标签视图，匹配；普通正确源常量缓存同样匹配 |

这是同源后续调用，不称未见法规泛化；本次单独1/1，不把原四例3/4改成4/4或整体就绪。程序及语义来自真实旧教师输出与原源文，年份/查询数值是原生问句字面量；没有借标签补程序。[执行封存](../../artifacts/rr_method_redesign_20261109/legal_scope_replay_v1_20261110/execution_closed_before_grading.json) · [随后评分](../../artifacts/rr_method_redesign_20261109/legal_scope_replay_v1_20261110/TRAIN_grade.json) · [原/恢复域及七项检查](../../artifacts/rr_method_redesign_20261109/legal_scope_replay_v1_20261110/adaptation_and_checks.json)。

预测封存后只读官方§63 Prolog源实现独立核对，其63(c)(7)(ii)确为年份到局部12000的谓词，不计算包含所有限制的最终个人扣除。没有读取官方case/TEST标签，参考代码不进入模型提示或恢复程序。[只读来源和SHA核对](../../artifacts/rr_method_redesign_20261109/legal_scope_replay_v1_20261110/source_implementation_review.json)。

### 普通函数能够完整生成，语义问题不能由类型或答案掩盖

旧PAL式法律路径仍要求项目的scope/rule/residual等声明。因此固定一次普通Python控制：只给原TRAIN8完整§63、已学九输入契约及原函数目标/签名，不给教师表达式、义务、case、query或答案；raw text、不附JSON schema，模型与OFF/采样/8192/32K均不变。普通赋值、分支和return精确转到原符号核，不运行生成Python。事前教师函数往返全域等价及坏代码拒绝检查通过。

Qwen在**9.211秒、2120输入/331输出tokens、stop、thinking OFF**完整返回普通函数。它通过语法、类型及实际执行，却有三种可核实的源误读：200%写成乘200；特殊期把18000用到应由C给出的12000基数；依赖人条款直接赋予`max(500,250+income)`，而非限制原基数。原七条义务5过/2反例，全域教师参考比较sat（不等价），程序**语义拒收入库**。这不是独立角色学习，也没有新增该执行模型的原生成功；提供契约的旧教师成本继续保留。

[完整真实函数和wire](../../artifacts/rr_method_redesign_20261109/legal_plain_python_v1_20261110) · [具体语义接纳决定](../../artifacts/rr_method_redesign_20261109/legal_plain_python_v1_20261110/semantic_admission.json)。本次只回答给定契约下的普通函数能力；不同于旧八分节摘要任务，不能分离估计每个提示改变的因果效果，也不据单例概括所有来源能力。

一个零调用软件探针只修复倍率和B/C金额这两处数值误读，保留错误cap赋值。该诊断程序即可通过全部原七条后置条件，仍在普通期、非联合、非head、dependent且收入10000时给10250，正确基本扣除为3000。完整参考比较继续拒绝。因此`all_supplied_obligations_verified`只能表示已给义务满足，不能升级为完整源语义证书；既有checker本来也没有这样的保证。普通`min(current, counterfactual_non_dependent_base)`已能修复这个孤立错误并与参考全域一致，不将它包装成新学得机制。诊断副本不冒充真实模型修复、不入库、不计新原生样本。[完整检查充分性探针](../../artifacts/rr_method_redesign_20261109/legal_plain_python_v1_20261110/checker_sufficiency_diagnostic.json)。

### 查新与阶段决定

SARA作者的[2021年讲义](https://a3nm.net/work/seminar/slides/20210909-holzenberger.pdf)已明确讨论条件反事实。既有数据包中的官方§2 Prolog会检查非H的替代关系路径，完整正确缓存能表达“仅因H成立”的区别；原固定TRAIN没有直接以该条款为目标的query，本次不把它当新原生机制触发，也未为此生成。这里只排除“保留理由本身是新增能力”的主张，不据直接目标缺失否认全部间接调用。

[Catala的scope/context/state](https://book.catala-lang.org/en/5-3-scopes-toplevel.html)及[例外语义](https://book.catala-lang.org/en/5-4-definitions-exceptions.html)已经能保留计算状态和组合例外。[2024年法条软件工程分析](https://law.mit.edu/pub/aidrivenstatutoryreasoning/release/1)还直接使用同一§63新基数与两倍计算。当前源视图和数值恢复作为公共组件使用；没有相对强对照的独立作用，不晋升两项贡献，不重试追分或启动完整建库。

本轮15项相关回归通过。新增模型1E/0T、无重试；另记一次原TRAIN85 oracle view（130→131），原标签只在预测封存后用于评分。已知增量executor API现金0美元，GPU成本及教师历史发票不可得，总项目实际费用未知。旧教师§63获取15314输入/3766输出tokens、81.914秒保留计账，不能把契约材料当免费来声称本次有独立成本优势。原四例、旧库、原始响应和账本全部保留，Goal仍active且未完成；未启动主训练、完整矩阵、TEST或论文。

[本轮结果/费用/保存核验](legal_scope_and_python_results.json) · [可重复审计](audit_legal_scope_and_python.py) · [15项回归](legal_plain_python_regression.txt)。

## 最新实质接续：源支持范围已获取，当前表示扩展不晋升

[当前目标](../../docs/CURRENT_GOAL.md)是唯一执行说明，[当前证据与下一项工作](../../docs/METHOD_REDESIGN_CURRENT.md)原位维护；下列协议和旧设计均为相应实验的历史快照，不另设执行队列。该次累计**1375E/59T计账、pending0**；最新累计见本报告顶部。

本次比较的是“谁可能为固定subject/year提供正151扣除见证”的获取表示，不能把可能支持误写为实际资格。实现了一个有限集合/TOP解释器、源分节效果摘要和独立集合成员SMT比较；未知相关输入保留TOP，金额变化/取消资格不能新增claimant。这个接口针对局部法律程序，不把自定义Unknown、全源形式证明或原87必须成功新增为验收门槛。

两个真实Qwen获取请求收到相同完整TRAIN151/152、角色说明及旧部分TRAIN程序，不发送case、query、答案或DEV事实。均完整stop，但分块组有非法变量、五处非逐字引文，把151(d)/152(b)误当正支持，且未产生deduction桥；紧凑组沿用旧部分程序的范围声明，含非法变量。后者原先因unresolved短路被误标结构通过，现用真实响应建立回归并修复，原始记录保留为错误的历史校验。旧材料与模型能力的分别影响没有被隔离，不能据此归因全部失败。

一次教师审查在本地strict-schema预检拒绝：`comparison`枚举缺少`type`，未发送模型。其失败尝试照常保留计账；没有删除或重置。改为显式string枚举并在计账前预检；已有unresolved也必须先检查表达式。两处修复均有真实失败回归，原v1全部绑定源码按seal逐字保存。

随后使用**原定教师源编译器**作有限控制：两组都只获相同完整151/152与输入族说明，去掉造成任务范围混淆的旧部分程序，不接收对方产物。没有调模型、采样、seed或executor thinking；这是既有教师角色，不是更换执行模型。模型角色与提示材料同时变化，只能说明这条编译路径可行，不能分别量化两种变化的收益。

| 实际产物 | 获取/检查结果 | 解释 |
|---|---|---|
| 教师分块摘要 | 八分节全覆盖；151(a)转发、151(b)自指/配偶、151(c)/152(a)依赖、152(c)/(d)关系/同住支持、151(d)仅金额、152(b)仅移除；结构/逐字引文/无循环通过 | 真实源获取，非手写正确摘要；仍以输入族确为保守上界为语义前提 |
| 教师独立紧凑表达式 | 表达式可执行；一条引文夹带`depending on how exact?`，完整产物拒收 | 不改引文、不将产物升级为成功；也不拿引文错误宣称摘要有机制优势 |
| 两组可执行集合函数 | SMT差异公式unsat，对全部抽象输入集合等价 | 这是表达式部件的离线等价，不是全产物获取平手，更不是NL忠实性的形式证明 |
| 原生执行 | 原四例预测仍3/4；本次未实际读取87锚点 | 手写参考锚点/有限域控制不计新真实主路径成功；无fallback计入 |

逐源语义检查与集合函数证明分开：151(a)/(b)/(c)、152(a)确保扣除见证来自自指、配偶或依赖路径，152(c)/(d)必要关系/同住覆盖候选，金额/排除只收缩资格。显式正法律状态单独保留；未知相关锚点仍开放。这个只读核对不是机械引用即正确，不证明实际锚点抽取已完成，也没有未执行的教师共同复核。因紧凑全产物未通过引文检查，原条件式共同复核未发送；不为凑通过重试。

教师分块输入16683/输出2229tokens、49.87秒；紧凑组15951/2284tokens、53.56秒。输出含reasoning子集，不能再加总；同材料输入的schema/提示表示有相应开销。单次3.69秒差异不是稳定成本优势，紧凑组总tokens更少。**当前表示扩展不晋升，不追加同目的获取；这不反证全部法律部分编译，也不以成熟算法自动否定方案。**

### 真正完成的工程与保留的缺口

本次31项相关回归通过，含真实unresolved漏检、旧审查schema拒绝、源范围开放、源码/源覆盖、原正负调用及保存恢复。原始响应、拒收记录及v1/v2绑定代码完整冻结；前1429条calls及全部meta/oracle逻辑快照剔除本次新增后仍为SHA256 `62339e3ea0357313d9ac923220bce86c43efde49fe60f7964cb1c5e08df89154`。没有新oracle视图、DEV回灌、TEST、完整建库或主训练。

独立作用仍是核心缺口：现有同程序缓存只是等价控制；新独立紧凑组件说明不需要分块表示来获得该集合函数，未建立一个额外表达能力。尚缺真实原生范围接口、未存目标的源编译与必要开发/跨库使用，但不能为少数源码检查设新零回退或全分支门槛。

继续零调用盘点了原固定24个SARA TRAIN源、8部唯一政策与当前14条学得规则的跨政策字面条件重复。151(d)(2)→63(c)(5)仍是已执行完整条件复用；151(d)(5)→63(c)(7)还共享年份条件，但法律后果不同，不能搬运源置零结论。通用短语重复不算另一成功；字面盘点也不能排除非字面迁移。[完整盘点](legal_contract_reuse_inventory.json)保留来源与匹配，未读case/grade来寻找优势。原TRAIN§2(b)(3)(B)还明确出现依赖成立理由的“but for §152(d)(2)(H)”；这里只登记需要检验的真实接口问题，未实现/未实测，不将它命名成已成立新贡献。下一项工作只在当前证据文档维护。

### 本次实际费用与请求

本次真实发送**2E/2T**，另1次教师本地schema预检失败未发送但计账保留，共新增2E/3T计账。E输入12049/输出1920tokens，请求耗时131.28秒；T输入32634/输出4513tokens，请求耗时103.43秒。已知executor增量API现金0美元，GPU和教师实际发票未知，总实际现金费用未知。重试0，教师服务内部重试不可观测；原账本不重置。所有新请求仅使用原TRAIN来源，executor thinking OFF。

[完整请求/费用/前后校验](legal_support_acquisition_results.json) · [复现脚本](audit_legal_support_acquisition.py) · [31项回归](legal_support_regression.txt) · [原执行器输出及字段失败](../../artifacts/rr_method_redesign_20261109/legal_support_acquisition_v1_20261110) · [教师独立获取与冻结源码](../../artifacts/rr_method_redesign_20261109/legal_support_teacher_v1_20261110) · [支持范围解释器](../../legal_skill_guard/rr/legal_support_ranges.py)。Goal仍active、未完成。

## 两项设计卡与法律近邻

| | 改进1：保留角色的跨条款接口 | 改进2：保留作用对象的例外闭包 |
|---|---|---|
| 真实瓶颈 | 旧§63接口把“他人为当前个人获准扣除”压成外部Boolean，隐藏claimant/subject/年份；生成模型还会调换当前查询个人与其子女 | 模型把“某条款适用”与“该条款取消一项资格”混为一谈，或让特殊置零与一般金额同时生效 |
| 具体机制 | 从TRAIN法条实际生成谓词签名、引用关系和具名规则；冻结来源条件；按原生问题投影未问参与人，实际连接事实并保留witness；证据不含参与人的输入记录拒收 | 从法条学习一般/特殊规则的优先边；依参与人及年份对齐相反结论或同键金额，压制被替代规则；冲突前提不向下游形成确定结论；适用性查询与效果分别保存 |
| 实现 | `legal_predicate_skills.py`、`legal_case_grounding.py`；真实源程序/模板库、确定性问句编译和输入证据检查 | 同一有限有支持模型求解器及真实教师源优先边；不是以样本答案选择输出 |
| 本轮真实证据 | 81连接Alice→Bob的dependent事实到151(c)；86以Alice为claimant、Bob为subject找到152(b)(1)见证。151(d)(2)的完整条件规范化显式引用后匹配63(c)(5)，复用其条件/角色，没有复制置零后果 | 72将Bob的2000通用金额压制为0，同时保留Alice的通用金额；去优先边时本例冲突。86的Bob→Charlie正dependent结论被例外压制，保留反向incoming见证；该效果变化没有改变86的适用性真值 |
| 最强简单对照 | 同信息正确政策缓存、源条件PBE/精确条件检索，以及共享源材料的直接模型 | 同信息缓存/普通优先规则推理，和只移除源优先边的消融 |
| 尚未知 | 超出正确缓存的获取/复用成本作用、未见引用结构上的作用；单次重复条件匹配不证明普遍泛化 | 超出普通正确优先程序的学习/修复作用；当前局部模块不覆盖整部法律 |

法律相关工作限定了可提出的主张。[SARA 2021 §2–3](https://arxiv.org/html/2105.07903v1#S2)已经把跨条款参数传递作为结构抽取，原执行基线接收标注结构；[官方代码](https://github.com/SgfdDttt/sara_v2/blob/main/code/argument_instantiation_models.py)读取映射再传递参数。本项目可以研究从TRAIN文本取得接口，不能称首次发现角色传递。[SARA法律信息抽取工作](https://aclanthology.org/2023.nllp-1.12/)也已连接案情抽取与符号推理，支持把实际抽取质量单列。

[Policy-as-Logic §3](https://arxiv.org/html/2608.11905v1#S3)已有一次政策编译、事实schema/映射、关系列表及ASP求解，所以“结构化抽取＋规则缓存”本身不构成差异。[法律DDL形式化工作§5.2](https://arxiv.org/html/2506.08899v1#S5.SS2)明确记录跨段落谓词不能重用的问题；本轮的统一接口及真实引用是针对这一问题的候选改进。例外优先和有支持推理采用成熟机制，贡献须由法律任务中的额外作用支持。本轮并未取得相对完整正确缓存的额外正确性或成本证据，因此不将两项候选晋升为已验收贡献；不是因采用已有算法而否决。

## 负调用已接入真实技能库执行，未将局部否定升级为原生成功

新增的`evaluate_guard`计算已学合同的源前提，与对一般Horn规则作逆否推理不同；不添加法律规则、事实或未知默认值。真实87中`deduction_under_section_151_allowable(Alice,Bob,2017)=False`现在可确定这个具体63(c)(5)调用的条件为False。旧前向head缺少负推导，只返回Unknown；新接口直接使用已观察负callee，**该具体调用不需要补译151(a)/(b)**。原native问题还对未问claimant作存在投影，仍Unknown，不能把Alice一人的负事实当全称否定。

`execute_library`已将这条路径接入保存的源库：81有Alice→Bob的正条件调用；86有正确incoming正调用及一个被例外否定的自依赖调用；87实际执行从151(d)(2)条件迁移到63(c)(5)的负调用。72仍使用实际源优先边与金额效果。四个原生预测全部与封存版本相同，未改评分。37项相关回归通过，包括真实角色/年份错误、缺观测保持Unknown及原生范围不可暗改；库冻结后加载逐项一致。

显式声明仅Alice的有限形式问题可得到False，但这是不同于原native投影的问题；加入一个未表示claimant仍Unknown。这些是接口边界/软件控制，不是新增TRAIN案例、oracle视图或核心成功。零金额受未知百分比削减仍为零的SMT义务也已检查；这是公共算术验证，不是新增学得技能或完整法律源证明。

[具体调用修复、前后结果及冻结代码](../../artifacts/rr_method_redesign_20261109/legal_guard_call_repair_v1_20261109/results.json) · [实际库入口与逐例调用](../../artifacts/rr_method_redesign_20261109/legal_library_runtime_v1_20261109/execution.json)。本次新增模型/oracle调用0，calls/meta/oracle完整逻辑快照SHA前后相同，累计仍1373E/56T。

### 费用与对照解释进一步核实

[按共同准备与边际执行的费用核对](legal_shared_cost_comparison.json)：实际共享准备为两笔教师源获取/复核（34653输入＋7469输出tokens，161.19秒）及一笔最终事实抽取（1735输入＋1272输出tokens，34.88秒）。完整共享直接对照另有一次10045tokens、15.97秒的模型请求，两条符号执行路径都不需要它。本次四例库执行一次CPU墙钟约0.13秒，非GPU计时，不作为稳定延时统计。

这项边际节省来自公共符号执行，**不能独归两个新法律机制**。反过来，同一库/同一代码的缓存逐例相等，也不是一个独立源获取策略的反证。当前控制确认了运行等价，尚未比较新源获取、模块选择与复用的独立策略；不将已有算法本身视为否决标准，也不据此宣布两贡献成立。

[原SARA DEV公开query目标的静态检查](legal_dev_target_coverage.json)显示局部库暂无匹配目标（0/8）；仅检查目标可用性，未读DEV标签、未把事实用于训练、未产生开发准确率或新完整评测。这不是要求八例全覆盖，而是说明当前三个TRAIN成功不足以证明原定开发链路已经接好。源编译仍须能利用冻结库处理未存目标；当前底层代码将人物角色硬编码为若干参数名，也有待在实际新调用接口上替换。

## 真实流程、修复和原生结果

首次生成前固定原128 TRAIN中的81、86、72、87四例，协议已保存。它们是**本次新选的四个已有TRAIN来源**，与此前20例小试分开；原数据集合、划分及旧20例结果未扩大或改写。研究者已见公共输入，所以是有目的TRAIN诊断，不称盲留出；同政策不能称未见法条泛化。

本轮6E/2T均结算，失败、截断均计数。旧source-only执行器程序完整返回6328输出tokens、175.34秒，但捏造自身适用前提、使用未绑定/未声明项，拒收；独立教师程序可编译。V1事实请求越过案情抽取直接输出法律结论。V2修复谓词/参数及查询投影后，仍在86反复枚举相同关系，8192输出tokens、228.47秒截断，原样保留。V3以固定四例、有界输入行及原始事实句子枚举阻断重复和引用query为法律事实，1272输出tokens、34.88秒完整返回。未调温度、seed、thinking或8192上限。

**V3格式通过不等于全帧语义通过。** 81的一个扣除记录引用婚姻句子，86/87模型query的参与人颠倒。原IR保持拒绝/错误记录。新公共路径独立从原始问题和已学角色签名编译query，不把错IR改写成“原模型正确”；中性人物/年份枚举由公共输入确定；实体证据检查拒绝81那一条无Bob的记录，保留其真实dependent输入再由源规则推导。没有补写缺失法律规则或加入TRAIN答案。87的显式负deduction关系按原极性保留。

下面所有模型请求、代码、库和预测均先冻结，之后才复用这四例原始缓存TRAIN标签评分；标签未进入生成、修复或教师提示。未打开TEST。

| 原TRAIN | 新路径原生预测 | 原缓存标签 | 原直接模型 | 完整共享信息直接模型 | 正确政策缓存 | 具体机制状态 |
|---|---|---|---|---|---|---|
| 81 | Entailment | Entailment | Contradiction | Entailment | Entailment | Alice→Bob，151(c)真实witness；拒收一条伪证据记录 |
| 86 | Entailment | Entailment | Entailment | Contradiction | Entailment | 正确incoming Alice→Bob；旧直接判断虽标签对，却以Bob有Charlie作理由。新例外闭包还压制Bob→Charlie的operative dependent关系 |
| 72 | Contradiction | Contradiction | Contradiction | Entailment | Contradiction | Bob金额0；去优先时2000/0冲突，原生结果未决；Alice一般金额未被误压制 |
| 87 | 未决 | Contradiction | Contradiction | Entailment | 未决 | 保留Alice→Bob显式负关系，不能仅凭它推出任意claimant均为负。原任务的依赖完成性/闭合语义尚未接好；不是新增必须取得完美负锚点的验收门槛 |
| 合计 | **3/4** | | **3/4** | **1/4** | **3/4** | 无fallback答对被计为核心成功 |

原直接与完整共享直接是两个真实OFF批次，不挑1/4者作唯一比较。更多正确上下文没有保证模型按规则判断，不据此断言新方法普遍优于直接提示。正确政策缓存对照使用同一原始教师材料、公共编译/证据检查与普通求解器，逐例重现新路径；它是实际执行的等价控制，**不是另一次独立全政策获取实验**。精确条件检索/PBE在本例也能取得相同guard，未建立对它们的额外作用。旧错误—修复检索/独立错误模型对照及负结果完整保留；当前候选不预测误读概率，不为凑对照新增标签通道模型。

### 本轮哪些已经解决，哪些没有

- 已解决：首个真实法律关系程序、显式角色/witness消费、未问角色投影、非法案情证据拒收、同键金额优先与带极性例外、库保存/冻结/加载精确恢复。这些均有真实源程序/事实记录，不是纯构造原型。28项相关回归包括真实坏输出、原查询颠倒、例外不得误伤其他人、无根循环与冲突前提隔离。
- 未解决：执行器自己生成源程序仍失败；87未得到原任务二分类结论；尚无独立未见法律引用验证或实际获取/复用成本优势。五库保留，本轮没有宣称Airline/ProofWriter迁移已验证。原始整帧语义错误不能被3个新路径答案掩盖。
- 范围限制：这是151/152局部条款及63(c)(5)完整条件的有限模块。151(d)(3)、152(b)(2)等未编译项保留未决；教师复核指出taxable year与calendar year一般不可混同，本轮2015/2017按原SARA日历年任务约定，不把这个局部接口称一般税年程序。教师未获63全文的优先边专项复核只审核151/152，63条件匹配另按本轮完整公共63原文检查。151(a)给出exemption到deduction的来源依据，不把隐含桥接称新学得独立规则。

这些未回答的科学问题及最新接续工作统一见[当前证据入口](../../docs/METHOD_REDESIGN_CURRENT.md)，本报告不再维护另一个执行队列。

### 执行说明归并后的实质接续：87零调用审计

当前有效目标/授权只在[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)维护，当前证据/下一项工作只在[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)维护；本报告保存科学证据，不提供另一个执行队列。长说明已备份，旧方案为历史参考。

[实际依赖切片与反模型](legal_87_closure_audit.json)确认两个独立问题：求解器对任何含null的存在查询都将refute固定为False，这是实现缺口；63(c)(5)所引整个151的局部库只有151(c)构造路径，151(a)/(b)并未完成。实际输入只有Alice→Bob显式负关系，当前接口未给出claimant范围完成性。两个SMT完成仅展示这份抽象可令未表示claimant关系为真或假，不是新案例/标签，也不说明原生SARA题目歧义。官方任务仍是二分类，不追加第三类验收或完美负锚点要求。需将原任务闭合条件与源依赖接好，不能统一把unknown改False。原四例预测/评分保持不变，新增模型/oracle调用0；金额输出的未编译条件边界也已记录，未作完整政策稳定性宣称。

## 原始证据、费用与保存

[首次协议](legal_interface_pilot_protocol.md) · [具体接口修复](legal_interface_followup_protocol.md) · [有界修复及停止重复规则](legal_interface_bounded_protocol.md) · [原失败字段路径](legal_interface_failure_audit.json) · [原坏对象离线拒绝](legal_interface_bounded_offline_evidence.json) · [28项回归](legal_interface_regression.txt) · [四例缓存TRAIN评分](legal_native_pilot_grades.json) · [逐物理请求账本与费用](legal_native_pilot_ledger.json)。

[真实原始源/事实/对照V1](../../artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v1_20261109) · [V2截断](../../artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v2_20261109) · [V3与教师优先边](../../artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v3_20261109) · [新公共路径逐例执行、拒收项及冻结库](../../artifacts/rr_method_redesign_20261109/legal_grounded_replay_v1_20261109) · [完整共享信息直接对照](../../artifacts/rr_method_redesign_20261109/legal_relations_shared_direct_v1_20261109)。V1/V2五份绑定源码均按各自seal逐字保存在frozen_source/；当前源码见 `legal_skill_guard/rr/legal_predicate_skills.py`、`legal_case_grounding.py` 及对应experiments。

此前法律关系小试封存时累计**1373E/56T、pending0**，该次6E/2T，不重置预算；最新累计见本报告顶部。E输入26662、输出19335tokens，请求耗时合计541.64秒；T输入34653、输出7469tokens（reasoning为其中子集），请求耗时合计161.19秒。执行器已知增量API现金0美元；GPU成本和教师实际发票不可得，**总实际现金费用未知**，不能写总费用0。客户端重试0，教师服务内部重试不可观测。原1421行calls及meta/oracle完整逻辑快照扣除本轮新增后与事前SHA逐字一致，旧冻结模型/预测/评分hash不变；原模型服务身份不变，无研究客户端。原五库、数据隔离、失败记录全部保留，不启动完整训练、完整评测矩阵、TEST或论文。

---

# 旧M1/M2及此前诊断原文保留

# M1/M2 真实TRAIN最小闭环与强对照

## 当前合并结论：尚未取得两项独立贡献的实证

**研究决定更新：当前M1配对树／源路径实例和M2四标签联合通道实例退出扩展队列。** 保留实现和结果供复现及对照，不继续把它们列为“补齐工程就能成立”的两项贡献；不扩完整建库，不为它们续购同类探针。这一决定只针对当前已测实例，不是证明所有语义消歧方法均无效。原Goal仍是两项实质贡献，active、未完成，尚未选出有依据的后继算法。

### 最新实际实现：组合表示缺口已排除，变体不晋升

本次不是泛化查新或重测原七操作模型，而是实现了原运输审计已经指出、此前未实现的具体组合：**读取另一个角色后，再将unknown误读成false**。原语法不能用一个固定函数解释83原文与受控例的相关回答。对原操作做完整有限语义闭包、按九种h上的函数表去重后有15个不同函数；最短描述成本仅0／1／2。没有为83手加规则、默认正确答案或新原语，unknown转false始终是被建模的读者错误，不是对真实事实的改写。

该集合已经对原一元操作的后组合封闭，因此在先读取一个角色的这类语法内，继续增加组合深度不会产生第16种函数行为。不用反复加深同一语法来追分；此结论不外推到所有可能的语义图变换。

[新学习实现](../../legal_skill_guard/rr/composed_reader_channels.py)实际拟合四回答联合混合，同时拟合同一闭包的逐字段对照；数据仍仅原71/79四条归纳记录。全部旧系数、残余质量、EM步数和上下文规则保持固定。13项相关回归通过：原七函数限制下逐点复现旧冻结预测，组合非交换性、原83真实失败、分布完整性、未问值拒绝和保存恢复均检查。模型及所有h条件分布已经保存并逐点加载恢复，未收入当前运行库。

以下仍是**对原已观察四例、两个排除TRAIN母来源的事后离线诊断**，不是新盲实验。研究者曾用83定位表示缺口，不能将它重新包装成独立确认集。

| 模型／同信息对照 | 平均联合NLL↓ | 唯一整组mode | 局部唯一MAP正确 | MAP且原完整源frame正确 |
|---|---:|---:|---:|---:|
| 新组合联合模型 | 2.534 | 2/4 | 3/4 | 1/4 |
| 同15函数闭包逐字段 | 2.689 | 1/4 | 4/4 | 2/4 |
| 同闭包未拟合先验 | 3.625 | 0/4 | 1/4 | 0/4 |
| 原七函数联合模型 | 2.458 | 1/4 | 4/4 | 2/4 |
| 无语法记忆＋普通矩阵回退 | **1.992** | 1/4 | **4/4** | **2/4** |

所有并列使用同一1e-12容差。新模型比同闭包逐字段模型的联合预测好，但没有超过更简单的无语法对照，反推局部真值反而下降。具体新增错误是88受控例：真实局部值`[1,1]`，新MAP为`[1,0]`；其余三个局部类别预测正确，其中83原文、88原文的原D源frame仍被拒绝，不因新模型而修改或接纳。83两点现有一个可解释整条轨迹的组合程序，只是表示可表达性，**不是从未见数据学得这一程序的成功**。更多可表达错误没有变成更好的跨来源推断。

因此，分类通道的一项实现限制已修复，但当前阻断仍是学习泛化及相对强对照的作用，不是继续加操作即可解决。标准函数闭包和EM不列为新贡献，本变体不晋升、不引发新真实请求，不继续扫描函数或系数。共享普通源程序原4/4、推理0请求的结果继续保留，不重跑。M1仍退出扩展，两项贡献Goal仍未完成。

[事前记录的离线问题及固定比较](composed_channel_protocol.md) · [完整逐例结果、版本空间及账本前后哈希](composed_channel_results.json) · [复现入口](../../experiments/rr_v2_composed_reader_audit.py) · [13项回归日志](composed_channel_regression.txt) · [保存的模型、预测与绑定](../../artifacts/rr_method_redesign_20261109/composed_reader_offline_v1_20261109)。新拟合耗时约0.146秒。本轮0E／0T，全部calls、meta、oracle逻辑快照前后相同；累计1367E/54T、pending0。无新增来源、标签、seed、配置扫描、完整建库、DEV矩阵、TEST或论文。

截至本次六小时检查点及随后的离线复核，**M1、M2均未通过原Goal的方法贡献验收**。有真实生成、TRAIN学习、保存恢复和跨母来源局部执行；缺的是相对同信息强对照的额外作用，不能把报告数量、接口修复或局部IR可执行算作贡献成立。当前累计1367 executor / 54 teacher、pending0；本次复核新增调用0，原Goal active、未完成。下文首轮的1362E/51T是该轮封存时点，不是最新累计数。

| 对象 | 已有可核验的真实产出 | 当前方法判断 |
|---|---|---|
| M1混淆对驱动编译 | 真实错误、教师局部核实、冻结的实体无关程序，在两个排除TRAIN母来源的四例执行，二标签3/4 | 普通同信息监督树逐节点相同；后续来源路径学习的配对约束也未额外排除任何候选。当前实现没有独立方法作用 |
| M2结构化误读通道 | 真实D/R轨迹、拟合、评分前冻结预测；原平均联合NLL2.458，统一保留并列后整组唯一top1为1/4 | 同原语逐字段模型NLL2.383；本次更简单、无角色误读语法的记忆回退对照NLL1.992。两者整组唯一top1均1/4、反推局部标签均4/4，尚无额外纠错或成本证据 |
| 原生任务与跨库 | 多支付事实IR的四事件经独立核实、作用范围聚合20597；OE两母来源四条资产金额直接抽取正确；真实词典和部分观测学习库已更新并保存 | 这些是公共输入与学习管线产出，普通对照相同；不是完整原生法律答案、跨库学得机制成功或双贡献验证 |

因此当前实例**不扩大完整建库或评测矩阵**。这不是资源耗尽、持续截断或一个尚未修好的接口阻止实验，也不是增加零回退/涨分验收门槛。已经排除的分支不靠继续购买同类响应或增加通用组件维持。后续若推进新真实验证，须先有现有证据未覆盖的具体任务问题与算法差异；不能只换名称、再生成相同局部标签或重测已看结果。

### 新增离线强对照与停止扩展的依据

直接复用原四条归纳记录、原上下文特征、原独立混淆矩阵及固定0.05残余质量：若`(h,context)`在归纳中出现，以其联合经验频率占0.95、独立模型占0.05；未出现则退回独立模型。没有角色复制/取反语法、额外特征或参数扫描，也没有把排除标签加入拟合。它对原四个已观察排除例的平均联合NLL为**1.991527689**，低于M2的**2.457809288**；反推局部标签均4/4，完整回答唯一top1均1/4。简单记忆与平滑足以吸收当前平均预测优势，不能据初始较弱三对照宣布M2成立。

本次还发现原top1脚本只取单个最大浮点值，将83受控例的数值并列视作唯一输出：两个模式概率为0.297232533037562918和0.297232533037563751，相差约8.33×10⁻¹⁶。原报告的2/4是这一单argmax口径；统一按1e-12容差保留并列后，M2唯一命中为1/4。此前将2/4解释为唯一top1优势不准确，现明确更正，原评分JSON保留不覆盖。该修正不改NLL、局部MAP或模型参数，也不追加正确性门槛，只避免用浮点打破并列制造差异。

这是**事后诊断，不是新的盲实验**：脚本先枚举全部h条件预测、再读评分行，只保证此次计算不把目标标签用于拟合，不能消除研究者已经看过旧结果的事实。条件h只用于预测分布的条件与评分，推断使用全部h候选，不把教师真值当输入。概率评分与源frame接纳继续分开，不计原生法律答案。

[可重复审计脚本](audit_reader_backoff_control.py) · [完整逐例结果](reader_backoff_control_results.json) · [账本及原拒绝核验](reader_backoff_integrity.json)。旧冻结模型、事前预测和原评分JSON保持不变。

同轮只读复核了先前已付费的§63教师记录：其请求目标明确是基本标准扣除，排除额外标准扣除，不能拿它支持“基本/额外扣除混合作用范围”新问题。拒绝发生于`module.domain`的自然语言字符串，不符合执行器所需布尔表达式；重现原拒绝并保留记录，不替模型补写domain，也不计成新方法机会。[原请求目标](../../artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109/seal.json) · [原拒绝响应](../../artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109/teacher_sara63_basic_deduction.json)。没有据此启动新路线或新增调用。

后续维护本报告的合并结论，避免把每项工程检查另写一份阶段报告。现有[数值绑定报告](numeric_binding_report.md)、[来源路径证据](evidence_path_followup.md)、[部分观测更新](observed_library_update_report.md)、[固定20来源状态](fixed_pool_source_status.json)保留完整原始依据。

### 验收解释修正：非零残余不是统计不可识别

本次继续复核原`decode_joint`与`identifiability`报告字段，发现它们把“未取得确定性源语义证明”与“统计不可识别”混用了：旧实现因0.05全支持残余，令所有案例`semantic_answer=null, unresolved=true`。**不应据此断言M2没有给出可评价预测，也不应为通过Goal新增必须取得零风险或完美关系锚点的门槛。** 在已冻结通道参数下，应比较不同h是否给出相同的完整回答分布；每个h对本次观察都有非零概率不等于分布相同。概率MAP及其经验错误可以评价，仍不能升级为自然语言形式证明。[ECED原文§2.2](https://proceedings.mlr.press/v54/chen17b/chen17b.pdf)也将MAP后验预测误差与调用成本分别定义，而不要求一开始将所有其他候选概率降为零。

零调用审计原封存的全部9×81分布后，M2在四例各自上下文中均有九个互不相同的h条件分布，最小两两总变差为0.4063–0.6088；普通独立模型和softmax同样能区分九个h，联合经验模型则有真实的分布等价组。**即使不拟合、只用原结构语法先验，也已经有九个不同分布**，因此条件可区分性不是学得的贡献。此处固定了通道参数，不证明h与未知通道参数能共同从少量轨迹识别，更不证明分布就是实际Qwen的真实生成规律。

原M2的四个唯一MAP仍为4/4；最大后验质量分别约0.714、0.703、0.475、0.360（83原文、83受控、88原文、88受控），没有把这些小样本、先验相关的数值称为已校准正确概率。普通混淆矩阵同为4/4。若再要求实际候选有完整、被接纳的源frame，两者仍均为2/4；原自然错误和缺失候选不靠概率推断补写。因此本次修正**撤销了一个过强的否决解释，没有新增方法效果**，两项贡献尚未满足原验收。

后续不为这四例购买“完美锚点”、新增投票或概率阈值扫描，也不把unresolved比例当作独立方法成败的唯一依据。仍需解决的是相对强对照的算法作用、完整原生任务以及可复用技能的实际作用；当前没有证据支持扩大已被吸收的实例。旧源码、冻结库、原预测、原报告数值文件及所有原始输出逐字保留，不修改旧decoder来重写历史结果。

[只读审计及复现](audit_inference_scope.py) · [完整分布距离、后验与来源分层结果](inference_scope_audit.json)。无新增模型调用、来源、标签、seed或参数扫描。累计1367E/54T、pending0，原Goal active、未完成。

### 继续实施什么、停止什么

本次在原记录和最近邻原论文／官方代码上核对了两个最接近的补救方向，均未发现值得立即实现的新差异。**没有把它们改名为M1/M2的新版本，也没有用构造数据或新的真实请求延长已被吸收的实例。**

| 可考虑的补救 | 新核实的最近邻与实际机制 | 对当前研究的决定 |
|---|---|---|
| 来源条件化的程序修复／参数化 | [REFAZER原论文](https://www.microsoft.com/en-us/research/wp-content/uploads/2017/04/icse2017-refactoring.pdf)学习有上下文的AST重写；[官方语法](https://github.com/gustavoasoares/refazer/blob/master/Tutor/synthesis/Transformation.grammar)及[归纳入口](https://github.com/gustavoasoares/refazer/blob/master/Tutor/Refazer4Python.cs)有上下文匹配、子树引用与编辑。[Getafix](https://arxiv.org/abs/1902.06111)学习一般到具体的编辑层级并按上下文排名 | 它们不证明自然语言源规则忠实性，但“加来源特征、共享变量、学习适用位置”本身不是剩余算法差异。当前唯一真实cap纠错还没有跨规则条件学习或相对正确缓存的作用，不实现新的通用repair learner |
| 给读者通道添加引用层、图或潜在开关 | [SERC§4](https://arxiv.org/html/2605.28837v1)已有事实／验证问题图、实体检查、三值证据状态和一次逻辑传播，属于训练外部验证；[Bach等](https://proceedings.mlr.press/v70/bach17a.html)已有噪声来源的依赖结构学习 | SERC没有学我们的读者误读机制，不能说它已完全解决该问题；但图表示或相关潜变量本身也不构成差异。当前无证据需要共同源图编辑才能超过独立预测引用／类别的同信息方法，不先堆更大的条件错误表 |

原始记录还需区分两个可观测层次：D71受控例的`domestic service`指针正确但类别错误；R79受控例引用交叉，而work类别仍正确。正确引用与类别串用可以同时出现，这**不自动否定类别路由模型**，也不能据此宣称已经学得整组源角色复制。此前四个类别错误仅两个兼容整束复制，其中一个仅null/unknown重合。当前类别模型有真实拟合和预测信号，缺少的是结构联合版的独立作用；为匹配这些记录增加彼此独立的引用／类别开关尚未提供新收益。

另对先前§63材料核对了原生查询：原TRAIN8是`63(c)(6)(A)`适用性，TRAIN85是`63(c)(7)(ii)`基本标准扣除；加上已保存的basic-only生成目标，都没有支持“基本＋额外扣除总额的上限定位”新机会。只读既有public TRAIN输入，不把这些来源并入当前20小试、重分归纳／排除组或打开新标签。ContractNLI两个既定归纳文本的查询均为逆向工程禁止义务；定义／一般保密义务的存在不能直接当新错误标签，本次没有为此请求模型或认定原生答案。

**阻断类型和最小调整。** 当前不是执行器停机、预算耗尽、schema未修好或少一层接口；它是当前算法实例相对强对照没有额外作用，且两个补救方向没有足够学习依据。不能靠放宽正确性、减少对照信息、增加同类样例或把共同组件算创新补齐。原Goal仍未达到，当前也没有一条可辩护的新算法已经准备好实施，不以本次查新／决定结项。

最小下一步是重新确定一个确有原生任务用途的学习对象和具体更新／搜索差异，随后在原数据、资源和隔离条件下做有区分力的小试。两项贡献目标不变，实施可以先集中验证一个机制；目前没有依据承诺两个新名字或申请更多额度。未有新增依据前，不重启当前已失败分支，不追加相同探针、阈值扫描或完整训练。这是研究上的止损决定，不是新的机械轮次上限、零回退或涨分要求。

---

## 首轮真实TRAIN流程与原封存结果

2026-11-09。继续原Goal，状态 **active、未完成**。本轮已经执行真实生成、学习、冻结和排除母来源验证；**尚不能据此确认两项方法贡献，也不扩大完整建库或评测矩阵**。

| 部分 | 已完成并直接复用 | 本轮新证据／仍缺什么 |
|---|---|---|
| 原研究 | 原128来源/六臂DEV、旧A静态等价与B普通连接吸收、最近邻核查 | 不重跑；原结果保留 |
| 规则模块 | 航空和§151各有学生/教师真实生成；§151漏上限反例与`min(100,程序)`离线修复 | 属于公共程序基础及能力控制，不是M1/M2成功 |
| 公共前端 | 精简payer/payee/activity/medium、三值局部分类、逐字指针检查 | 真实20E均完整结束；2个排除案例的直接frame仍未被接纳 |
| M1 | 实际错误、教师核实、实体无关判别程序、冻结后真实执行 | 局部成对正确3/4；同信息普通树完全相同，额外机制未成立 |
| M2 | 真实四回答联合轨迹、结构通道拟合、事前全部h条件预测、真实排除来源 | 有学习与预测信号；同原语逐字段模型吸收平均预测收益，尚无额外正确语义答案 |

执行依据是用户提供的[最终设计与查新](external_design_snapshot/README.md)和[衔接清单](external_design_snapshot/server_alignment.md)，固定main `5368150eceece401ee475370cc6b8170ca6584bf`。中间被否决设计不恢复。没有新增母来源、seed、配置扫描、TEST读取或论文；执行器thinking OFF。教师沿用已有配置，本轮未改模型或采样。

## 真实流程和信息边界

[事前协议](M1_M2_pilot_protocol.md)从原TRAIN锁定20个母来源，第一阶段只运行SARA71/79/83/88。71/79用于学习，83/88排除于归纳；每母一个原文和一个预定单span变体，母来源总权重1。其余16来源尚未运行，不能计作跨库验证。

局部任务是Alice向Bob支付报酬对应的**工作活动和支付媒介**，没有评价整道SARA法律问题。加入`in hay`是受控事实完成，不把原文缺失的媒介补成已知事实；不沿用变体的原基准标签。教师核实的是源文本局部关系，不是程序自动证明或测试标签。

每例两个实际请求：直接frame组D、局部问题组R；联合观察顺序为`D.work,D.medium,R.work,R.medium`。学习侧8E及2T完成后，同时冻结M1、普通树、M2及三种错误模型，随后保存全部9种h上的条件联合预测，再获取排除来源的D/R/检索12E。最后封存各臂实际决策，再以2T核实排除来源。教师评分不进入学习、候选、检索提示或参数选择。

- [真实训练错误与冻结程序](M1M2_freeze_receipt.json)
- [完整冻结学习产物](../../artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109/frozen_learning.json)
- [事前盲预测](../../artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109/blind_predictions.json)
- [评分前封存决策](../../artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109/execution_closed_before_grading.json)

## M1实际学到了什么

学习数据包含真实错误：71受控例抽到`domestic service`却把工作判成农业；79原文将`wages`当媒介且局部问题过度unknown；79受控例的工作/媒介证据交叉引用。教师逐一核实，原始输出不改。被学得的有限程序是：

```text
读取实际R问题组的work回答：
  false   -> 预测(work=false, medium=true)
  true    -> 预测(work=true,  medium=true)
  unknown -> 预测(work=false, medium=unknown)
```

该程序无实体、金额或来源ID，确实在排除来源执行，但媒介部分利用了训练小池中的关联。88原文工作为农业、媒介未说明，程序错误预测媒介为农业产品。它没有学到普遍有效的角色绑定约束。去掉混淆对项的普通监督树得到**逐节点相同**程序，因此本轮差异不能归因于混淆对；教师提出的新问题也未被伪装为已问过的回答。当前四槽程序只是该设计的最小实例，不能据其失败宣称整个方案已被否定。

## 排除母来源的结果

每列分母为4例、2母来源；未知是独立语义值。源引用合格指逐字命中检查，仍不自动证明角色关系。

| 方法 | 局部二标签正确 | 源引用合格且二标签正确 |
|---|---:|---:|
| 直接角色抽取 | 2/4 | 1/4 |
| 正确政策缓存＋实际抽取 | 2/4 | 1/4 |
| 局部问题R | 2/4 | 2/4 |
| M1编译程序 | 3/4 | 3/4 |
| 同信息普通树 | 3/4 | 3/4 |
| 同材料错误—修复检索 | 1/4 | 0/4 |

检索臂得到归纳侧全部原文、D/R错误和核实frame/说明；没有减少其材料来造弱对照。当前正确政策缓存不会取得oracle事实，该局部任务下与直接role分类等价。M1/普通树只实际消费R组，均按1请求/例计；直接抽取、缓存和检索也是1请求/例。检索未消费当前D，因此不虚计成两个必要请求。M2及所有错误模型消费D+R两个完整问题组，不能把批内各字段当免费独立请求。训练和评分成本另列，不从单次推理成本中消失。

| 来源 | 教师核实局部真值(work,medium) | D原始分类 | R | M1 | 主要原因 |
|---|---|---|---|---|---|
| 83原文 | false,unknown | false,false | unknown,unknown | false,unknown | D补造`money`，frame拒绝；R漏显式工作信息 |
| 83受控 | false,true | true,true | false,true | false,true | D把hay属性传到工作；角色span本身正确 |
| 88原文 | true,unknown | true,unknown | true,unknown | true,true | D把`wages`当活动、补造`cash`，frame拒绝；M1媒介关联外推失败 |
| 88受控 | true,true | true,true | true,false | true,true | R把明确hay判false；检索改写源引文而拒绝 |

没有将拒绝的`money`/`cash`改为正确null，也没有修补检索引文。原四标签仍可作为真实阅读器观察评分，但**不能恢复成合格frame**。最初离线评分器只接受合格指针，不能处理真实拒绝记录；新增只读[证据评分器](score_real_TRAIN.py)明确分开原始分类与接纳层。冻结学习代码、参数、提示和盲预测逐字不变。

## M2学到了什么、没有证明什么

M2用两母来源的真实轨迹拟合7种角色读取/极性/unknown原语的2401种四字段联合组合，并保留identity及0.05未解释噪声。原语词汇、EM和MAP均为公共组件，不算学得技能或独有算法。拟合的权重与上下文适用性才是学习产物。

冻结模型对排除来源四个回答的联合分布评分如下。负对数似然越低越好；本轮没有超参数扫描。分母太小，不报告显著性或泛化保证。

| 事前冻结模型 | 平均联合NLL | 原脚本整组单argmax命中 |
|---|---:|---:|
| M2结构化联合通道 | 2.458 | 2/4 |
| 逐字段三值混淆矩阵 | 3.522 | 0/4 |
| 同h/上下文联合经验模型 | 4.209 | 1/4 |
| 同特征非结构化联合softmax | 3.820 | 1/4 |

优势集中在83的两种观察：它们分别复用了79原文与71受控例的h/四回答模式。88原文是归纳中未出现的`(true,unknown)`，其NLL为3.848；88受控的R错误也未被所学复制模式解释，NLL为3.666。两例均差于独立混淆矩阵。不能把旧模式迁移误写成已解决任意新误读。

为区分学习与内置语法，另做一次**事后、零调用**归因检查，只用原归纳数据拟合，不调整冻结臂或阈值：

| 事后固定诊断对照 | 平均联合NLL | 整组top1命中 |
|---|---:|---:|
| 同一结构语法、不做拟合 | 3.133 | 1/4 |
| 同一误读原语、逐字段分别学习 | 2.383 | 1/4 |

所以有真实学习信号，但结构联合版未在平均NLL上胜过采用相同原语的简单学习器或后续无角色误读语法的记忆回退。原脚本单argmax报2/4对1/4；统一保留概率并列后，M2唯一命中仅1/4，与本次无语法记忆回退相同，不能声称有一个唯一top1优势。新对照及口径修正见本报告顶部，不混作事前注册臂。通道操作也仍多解：两个角色取值相同的正确轨迹不能证明复制方向，主要错误类型各只有一个归纳母来源的判别性支持。

相同公共MAP解码下，M2与独立混淆矩阵均得到局部标签4/4，**没有额外答对**。其中只有2/4有合格且覆盖正确活动/媒介的直接角色候选。原实现的保守证明字段均为unresolved；它只能说明未有确定性源语义证明，不能据全支持噪声断言冻结统计模型不可识别。MAP是可评价的统计预测，未算语义证书；后续口径修正和精确分布检查见本报告顶部。不新增“必须零错误”的验收门槛。

## 费用、实现与保存

本轮M1/M2共 **20E＋4T**，全部结算，无失败重试或同请求重发。执行器20次均`stop`，总输入8006、输出1349 token，请求耗时合计36.969秒；教师输入58923、输出2936 token，请求耗时103.771秒，reasoning1535为输出子集，不重复加总。执行器本地服务无逐请求API现金费用；GPU分摊和教师账单不可取得，实际金额记unknown，不能报总费用0。客户端配置retries0；供应商内部HTTP重试不可观测。

原Goal起点1339E/43T，当前累计 **1362E/51T、pending0**。31笔增量包含前期模块/重型前端7笔及本轮24笔。原1382行请求、184项meta、130行oracle逐项保持不变。原52份前阶段工件重校一致；原128/六臂的2859文件核验收据和全部原始结果保留，本轮未声称又逐个重算旧实验。

- [完整结果与逐例分数](M1M2_real_TRAIN_results.json)；[事后归因](M1M2_learning_attribution.json)
- [请求账本增量](request_ledger_delta.json)；[token/耗时/费用](cost_snapshot.json)；[保存核验](preservation.json)
- [生产学习实现](../../legal_skill_guard/rr/semantic_learning.py)；[生成入口](../../experiments/rr_v2_semantic_disambiguation_pilot.py)
- [7项学习回归](M1M2_learning_regression.txt)；[20项真实证据顺序/原始失败/冻结核验](M1M2_evidence_integrity.json)
- [完整原始请求与输出目录](../../artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109)

## 阶段决定

当前实例的M1作用被同信息普通树吸收；M2有可复用的预测模式，但还没有胜过同原语简单学习器的明确附加能力或成本价值。这是**贡献证据不足**，不是资源耗尽、截断或需要放宽正确性检查。具体工程问题是评分器原先未分开拒绝frame与原始分类，现已修复；其余拒绝来自模型输出。验证缺口是完整源解释/任务和跨库复用，而不是要求所有样本零回退。

已继续完成[现有真实轨迹的离线可识别性检查](M1M2_identification_gap.json)：三个归纳错误分别有2、6、2个同样简单的原语解释，不能唯一认定角色复制。例如79受控例的R媒介错误既可解释为读取工作，也可解释为媒介极性翻转；88受控的真实观察支持后者而反对前者。该排除观察仅用于诊断，未回流拟合。增加同h/同回答的重复轨迹不能补齐这个缺口。

下一步仍在现有固定池和设计内，先具体实现/反证来源绑定的判别操作及能区分上述竞争解释的实际问题；M2若只是上述简单误读学习器的换名，不继续购买同目的响应。只有给出明确、未被已有强对照覆盖的问题，才进行必要的新真实小试。不把已看过的83/88重新当盲确认集，不重复本轮检索/错误模型试验，不扩完整建库，不重开选题或Goal。目前无需新增资源授权。
