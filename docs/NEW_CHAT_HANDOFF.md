# 当前Goal恢复：从真实反例后的修订继续

模型切换后的恢复记录：get_goal 已核实同一研究目标恢复为 `active`。Qwen3-8B 服务及配置已核验。全局 Codex 模型已变为 gpt-6.2-sol，项目改从 `configs/legal_skill_convergence_teacher_v1.json` 显式绑定原教师 gpt-6.1-sol/high。教师复核为只读，无新教师调用。

工具会话 40235 已终结。固定控制命中历史同 wire 记录，关系提示新增一笔本地推理，仍出现原州籍极性错误。读者指针指向 3b0464…，其精确绑定源码已封存。

最新已结算任务为固定 TRAIN 20 母来源共同 B0，对应工具会话 97558，读 `handoff/pilot_b0_current.json` 的真实状态和绑定。24 个逻辑读数含四个 OpenExempt 母来源各自独立的 EC 与 EV。若已完成则复用结果；运行中保留绑定源码。MAUD 两版和 Diversity M2 补丁比较均为终态，详见 DEVELOPMENT_EVIDENCE_20261118.md。

先读AGENTS.md、PROJECT_MAP.md、docs/CURRENT_GOAL.md，调用get_goal；不创建/重置Goal。固定方案reports/legal_skill_convergence_20261117/，上游37a76ff。旧方案只作资产与失败证据。

每次压缩/中断后读artifacts/legal_skill_convergence_20261117/handoff/run_state.json及最新pointer，核对实际进程、工具会话、账本reserved、冻结绑定和terminal。从未完成处继续，不凭旧PID或计划重启任务。实际账本计数及在途响应以 run_state 和对应的当前指针为准。M2 补丁比较结算时累计 12455 条，当前 Goal 物理请求 28 次（教师 2、Qwen 26），共 140185 tokens。B0 用量继续在原账本累加。服务原PID536850/537626保留，Qwen thinking OFF；教师gpt-6.1-sol/high已真实验证。

## 必须保留的真实结论

Diversity-6学习母来源d201b0…：工程修复后固定接口错误/不忠实，联合关系正确/忠实；两个混合配置也未通过。四候选实际配对后，库选联合关系。Diversity-5另一母来源03d239…：预先选择的所学模板实际执行，但同州籍比较错读为true，原生错误；固定接口正确/忠实。不能只展示首例，当前无总体收益证据。

Goal目录下的不可变阶段：
- source_audit_01/e38bce316d85c79bf57edf72d264e2bf36e198de4a4861096bdce574541ba563：1次教师源审终结，58效果/59例外引文过，缺16项引用、无真实歧义。引文过不等于法律真值闭合。
- diversity_reader_probe_01/18332fc82acbf5eaacb06fa64bdd6996dbff04edc82644f75c64d30ac84a71ef：共同工程修复前2次拒绝，source_snapshot12文件封存。
- 同父目录9a28210778704b982ffd5c9b77aa09a22867d589364108632afbfe70decdc2cb：共同修复后固定vs关系2次终结，source_snapshot12文件。
- 8e876932dd6cd9b4f22d874608ebd5ddc0d4648e158b47f4bac6c3166ac127fd：四候选终结，精确复用上述2份有效wire，仅新增2混合读取。
- actual_interface_library_v1/c40b513f3ff9c985eed9fb9207ebb93d6c38a11d5adaf31cf776bbef56ded71c：实际库保存/恢复及新母来源读前选择。
- diversity_reader_probe_01/add5766667c7aec93f6d55098133bb0432a26f16b02f8648b29840af9401843c：另一母来源实际复用已终结，负结果，source_snapshot14文件。工具2038已exit0，不能重复启动。

旧工具会话86997、86319、38407、2034、2038均已终结。不可用当前已改的probe脚本重跑旧binding；用各source_snapshot或公开提交重现。目标是继续未完成修订，不重复已有记录。

## 代码与下一项实质修订

residual.propose是原合成器的扩展；relational_program/diversity_relational是真实组合接口；formal_training.RelationalInterfaceLibrary是真实配对读数、源忠实性、保存/恢复/新母来源选择。模板版本已绑定提示和执行器。旧观察保留，新模板排除无版本及版本不匹配的观察。AST 极性提示改写已完成。实际同一 TRAIN 错误未消失，后续要从主体绑定或结构化极性入手。

shared_semantics是新M2，旧风险选择器不用。diversity_supervision 有真实源编辑和派生闭包。完整读取条件下 K 为单解释。四个预选 TRAIN 来源上的受控遮蔽可以从原文变更产生非平凡共享事实关系，未发现自然歧义证据，也未执行真实补丁。新选组逻辑能够识别每组单独允许、联合时无共同解释的候选签名。下一步需接真实合同作用域及独立K/非平凡共享组和教师更新，不能捏造歧义或把拒绝全部更新算收益。保留177审计、失败和连续账本，不另开题。

## 数据、公开与复核

固定名册128/80/160，CNI17、MAUD3，MAUD TRAIN23/72语法section扩展；旧审计输入变更须复核。读normalized_inputs_current/diversity_train_current/diversity_holdout_current/contract_nearduplicate_current获取版本。不要打开sealed_test或sealed_native，不要全目录搜索原始数据。名册锁定回执为 sealed_source_roster_current.json，模型和技能库的 B8 冻结独立完成。未做 TEST 评分。

633e0e296cbfde8819a0d2c786b9cddc9bf379fa 已公开并核对分支引用；后续复用负结果、成本与离线重放器当前以本地包为准。重放命令python -m experiments.convergence_replay_public_evidence，已0新调用重现10逻辑解码/8物理响应并核150文件hash，不需私有账本或原始缓存。包只含公开TRAIN，不含DEV/TEST封存、整库账本或凭据。

曾因疑似私密合同外发被自动审批拒绝；官方公开MAUD data.zip的Git blob74dc33bf4b8720df325d2858ea74c2790f16db20与本地完全一致，本次每段请求亦是公开原文切片证明后，同一动作重新审批获准，当前无待用户授权阻断。不要重问已授权目的地或资源。

公开Git使用已验证公开父提交为parent的临时bare repo，不上传本地私有历史，不force/main。第二版prepare曾read-tree超时但未写远端，改用父提交对象缓存已解决；不因只读核验网络失败重推。保留所有无关dirty文件。

从共同 B0 读完后逐来源误差继续配对修订和完整小试。下一阶段沿既定方案完成 128 来源八批矩阵、DEV 曲线、冻结 TEST、消融和迁移。英文方法与开发结果初稿保存在本地 paper/METHODS_AND_DEVELOPMENT_RESULTS.md。当前Goal active且未达成，不以交报告或跑通机制宣布完成；有证据+实质变化+可检验预期才继续，不设置虚构优化轮次上限。


## 最近运行核验

MAUD Knowledge Definition 固定四母来源的配对已结算。引用版固定与合成各 0/4，共 6 次长度拒绝。标量版保留前三母来源的六次合法读数。最长来源展开语法请求超时，保留在账。用等价因子化语法只补最后一对，语法从 234214 字节降到 4125 字节。八次合法输出均为 unread，固定与合成各 0/4。八个参考输入仍通过生产链。格式故障与读者未能绑定判定条件已区分。会话 96236、52359、4568 均为终态，各绑定已封存，不重复读数。

ContractNLI 四份文档、68 项原生假设的公共证据布局已验证。分类 30/68→36/68，证据 F1 0.0276→0.3571。之后各臂共享此布局。Airline 两个真实配对仅发出两次编辑请求，原始控制精确复用。两例实际费用差均为 0，违反独立编译的 −70 关系。从实际反例继续教师补丁，在同一原生任务和衍生组比较普通与关系选择。会话 66775 已终结，见 `handoff/remaining_TRAIN_probes_terminal_20261118.json`。

OpenExempt 自然所有权会话 43131 已结算。固定 B0 精确复用，一次教师 gpt-6.1-sol/high 与八次新 Qwen。两条补丁及原技能原生 EC F1 均为 0，普通和共享均保留原技能。源审保留所有权真假两种可能。修订门控要求字面断言在全部解释中成立，零次新调用复查了原六项所有权断言，均不受源文支持。原运行的共享兼容结论保留。见 `handoff/natural_OE_runtime_followthrough_20261118.json`。

五臂冻结入口要求完整 B0/B1/B2/B4/B8 DEV 和同一 B8。DEV80原文与 TEST160身份元数据已核验。正式训练及冻结 TEST 尚未启动，TEST 原文和评分保持封存。定向检查 75 项及两个子检查通过。论文工作稿已记录共同 B0、真实 M2 诊断与 MAUD 输出处理。

当前连续账本 12510 条，0 条在途，当前 Goal 增量 83 条，累计已计 Qwen 396280、教师 79894 tokens。失败请求保留且单列。远端研究分支最新核验至 `633e0e296cbfde8819a0d2c786b9cddc9bf379fa`，新结算结果待同步。保留177源审、旧运行及全部暴露记录。
