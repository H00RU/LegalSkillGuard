# 五库混合学习当前执行证据

当前Goal保留且已按用户要求暂停，依据[统一方案](../legal_five_dataset_amendment_20261110/PLAN.md)及唯一[当前执行说明](../../docs/CURRENT_GOAL.md)。本报告原位更新，不构成新的目标或调用队列。

**2026-11-11用户请求暂停。** 全部相关任务及本阶段推理服务已停止，暂停后新增调用0，最终1893E/74T、在途0。当前Goal未完成；只有用户明确恢复后才接续。完整截至当前进度、真实方法限制、DEV停点、费用与恢复说明见[暂停报告](PAUSE_20261111.md)及[库存快照](pause_snapshot_inventory.json)。下面保留已完成阶段的科学证据，不是自动启动队列。

2026-11-11更新：共同初始化和第一轮四获取模型/三组合头的真实训练已完成，七系统首轮DEV尚未完成，现已暂停；完整三轮和阶段复核仍未完成。四获取臂均处理固定256来源、32次参数更新，耗时约594–612秒/臂。它们共用43,646,976参数LoRA配置及共同起点；教师在当前MIX阶段新增0，原始8B冻结。源日志、权重和优化器保留在同一运行目录，不重置账本。

[真实逐批训练轨迹](learning_trace.json)及[CSV](learning_trace.csv)已从原始日志导出：首轮四获取模型各32点，三个组合头各32点；逐库在线TRAIN损失、累计原生/核心梯度来源量和非零四格分别保留，新增模型/教师调用0。损失点来自各批实际八来源，任务构成会波动，不能当作固定DEV能力曲线。固定DEV每个epoch完整评估一次，尚未完成的点不填数、不插值为已测成绩。

当前技能学习对象按统一方案为模型参数与来源可追溯语义表示：LoRA获取器学习源局部语义，组合头学习连接评分。AdamW每累积8来源更新参数一次，不是调用技能教师或新增一条文本技能。教师配置保留，本MIX阶段新增调用0；普通原生监督梯度、M1额外局部信用与M2额外交互目标分别记录，核心学习是否成立由语义质量、实际使用和强对照判断。

[批次、来源配比与梯度证据](mixed_batch_sampling_audit.json)：每次前向1来源、累积8来源更新，256/8=32有效批次/epoch；方法三轮96步，另有共同初始化32步。首轮4/32批恰含全部五库，但无放回打乱保证每库全覆盖。来源比例50%/12.5%×4；不等于tokens/有效语义信号比例。四获取臂全部256有非零原生监督探针梯度，M1核心梯度仅3个ProofWriter来源，法律库核心信用更新尚无。普通监督loss降低不能证明M1跨库贡献。

[同缓存单补全/平均/稳健分析](first_epoch_credit_analysis.json)进一步限定首轮M1证据：4个稳定块全是ProofWriter原生结构已独立固定的单补全，真实多补全稳定块0；三种规则在全部现有可评分表上的决定相同。60个非空表只有56个`[0,0]`和4个`[0,1]`。此时M1与MML弱目标在数学上分别为零或同一二选一负对数概率；[原始表/梯度与权重核验](first_epoch_M1_MML_observed_equivalence.json)的梯度探针最大差5.96e-8。两权重文件仍有数值差异（相对L2约.02255），不得把分数差异归因于首轮并未被数据区分的跨组合机制；不作算法全局等价结论。法律来源的局部语义错误率尚不可判定，不填零冒充正确。

合同既定[证据使用/替换诊断](contract_evidence_probe_config.json)在最终epoch3冻结：原生成证据、移除、同位数ID桶内循环替换，固定原文、假设与模型自己的标签；只测相同标签的条件likelihood，不替换主结果、不把似然敏感性充作完整合同图/M2证明。[16份既有合同、48个token化变体离线核验](contract_evidence_probe_offline.json)保持标签、证据基数和范围，检查不读取gold标签，新增模型前向0。真实诊断将在固定矩阵完成后进行，并另记本地前向成本。

M2实际训练表：Norm1530四格、1104非零定向交互，ProofWriter505/35；Airline3/0，SARA0；ContractNLI结构oracle掩码不变。它们是训练机制覆盖，不是DEV收益。原生Horn次序、alpha与公共事实顺序不兼容通过[原始响应离线回归](horn_codec_offline_regression.json)修复；57条已付响应逐条核hash，未新增调用，原生48闭包不变。

DEV初次并发8暴露8条SARA HTTP600秒超时。账本中断边界1781E/74T、在途0，失败保留；核实服务无running/waiting后以最多4并发继续未启动项，超时请求未重发，失败主路径与原定fallback分开计。恢复控制器另行绑定，原冻结代码/配置未改；[恢复离线回归](dev_transport_resume_regression.json)核验失败不重试、仅新项派发及tuple/list配置等值。暂停前后续物理请求连续入同一账本，不把HTTP时间和当成GPU墙钟。

采样的相关参考：[T0 §5](https://arxiv.org/abs/2110.08207)合并打乱并限制大库采样权重；[Flan Collection §3.5](https://arxiv.org/abs/2301.13688)专门比较混合权重。它们说明混训通常使用明确配比，而不能证明本轮batch8或4:1:1:1:1最优。本轮按冻结协议完成分库16 DEV、逐epoch曲线与机制覆盖，不因同一批DEV随意改配比。

128条NormBench生成已有126条通过严格原生解析/执行，但[TRAIN逐来源语义审计](common_norm_TRAIN128_audit.json)整图仍0/128，跨度F1=.2290、typed-content F1=.09230、父边F1=.03006。这是共同初始化水平，格式成功不计方法学习成功。SARA官方参考原例32/32一致；[原始参考审计](sara_native_reference_audit.json)只用于TRAIN监督/评分，不是预测工具，旧22/32及运行库/路径失败保留。

已接好局部模型替代→共同合法补全→独立原生误差表→真实LoRA梯度的调用路径，以及同信息MML/HardEM/执行过滤；组合头共享缓存、原生评分与同容量SQLoom对照。当前尚无完整DEV方法收益结论。软件证据包括[packed likelihood等价回归](packed_credit_regression.json)、[原生匿名实例/四格回归](native_composition_alignment_regression.json)、[作用域去重回归](native_scope_regression.json)和[强对照回归](acquisition_control_regression.json)。其中原子匿名ID不能因序列化改变而计语义错误；同一可交换算子的显示重排不能充作多上下文；执行过滤使用跨全部共同补全的执行向量。

ContractNLI原始响应暴露证据数组重复循环。公开数量上界修复后的两条原截断记录分别984/460 tokens完成17个不同假设。中间位串编码保留原始记录，但正式训练采用更直接的稀疏原生句段ID集合与无损编号原文段，避免让模型额外数位置；[48合同离线检查](contract_sparse_offline.json)没有增加标签或改变证据集合。当前来源批次结束前不改其冻结文件；之后只作确定性转换，已完成来源不重生成。原生标签、证据评分、失败分母、TEST封存均不变。

已核验256 TRAIN/80 DEV/160 TEST身份；TRAIN为NormBench128及其余四库各32，合同恢复全部17假设。四旧库原始公共输入hash一致，ProofWriter开放48来源的参考Horn闭包与原生答案一致；Airline参考评分只在开放TRAIN/DEV侧执行。没有新打开TEST文本或标签。旧DEV每库8来源已有开发暴露，明确保留为开发，不声称盲测；固定TEST候选未在当前实际请求账本中发现调用或oracle暴露，仍待下一阶段授权。

NormBench保留指定128 TRAIN不变；按直接司法解释谱系合并，3 DEV与5 TEST身份从原同名分区的未选条目替换，未按模型成绩筛选。详见[谱系修正](lineage_reconciliation.json)。原始候选及全部历史清单未覆盖。

[原生适配核验](native_adapter_audit.json)和[token长度核验](native_tokenization_audit.json)记录实际字段及掩码。训练源最大8818 tokens，没有截断。ContractNLI17接口使用明确记录的运行时格式：已核对旧文档hash与官方全部17假设/证据，另存新输入hash；未将未公布序列化方式的桌面17任务hash冒充已复现。

共享内容/来源视图、原生节点、普通组合与定向四格实现继续复用；新增M1局部信用及MML/HardEM/执行过滤目标已接入独立模块，必要梯度回归通过。它们目前是代码与离线回归，不能计作真实方法收益。共同原生初始化已完成：256来源（Norm128、其余各32）全部记录非零来源梯度，32次优化器更新，耗时473.187秒，训练43,646,976个LoRA参数；原始8B权重未更新。全部七系统使用这一相同初始化；四获取模型和三个组合头已完成第一轮，继续剩余两轮。权重哈希见[共同权重清单](common_weight_manifest.json)，曲线见[实际优化步](common_optimizer_steps.jsonl)。

随后5条真实TRAIN原生推断均EOS结束、无截断，初始执行账本1410→1415、教师仍74；两轮定点复核另计4次，当前1419E/74T。它们不是DEV：SARA这一条答对，合同11/17，Airline这一条错误；Norm返回未定义中文规范类别，ProofWriter返回了错位原子格式和缺括号。完整[原始输出](common_native_smoke.json)、[逐来源审计](common_native_smoke_audit.json)及[请求账本差量](common_request_ledger_delta.json)保留。不能以4/5 JSON可解析冒充语义通过。已据真实问题补明枚举/原子示例，并为所有比较共用原生JSON grammar；256 TRAIN目标通过schema检查，五个grammar均已在本地xgrammar编译通过，第二次真实复核暴露了后端Unicode枚举乱码与ProofWriter重复规则循环，未批量追加同一失败请求；原始结果见[v2复核](native_schema_v2_results.json)。进一步以可逆ASCII角色码和公开事实/规则列表上界修复，全部TRAIN目标及五库实际目标token＋EOS通过grammar回归。[v3真实复核](native_schema_v3_results.json)两项均正常结束、通过类型和执行：ProofWriter闭包为Unknown，与原生TRAIN答案一致；Norm可执行但跨度F1仅0.2353、整图错误。它们只定位工程主路径，不能充当M1/M2收益或整体训练就绪结论。原共同初始化保留，不按失败样本补造语义或重复初始化。

尚未完成：后两轮方法训练、完整M1非Norm与M2实际推断证据、七系统曲线/逐来源DEV结果与阶段复核。Goal保持paused且未完成，不以本次报告或准备状态结项。TEST与论文未启动。

实际标准Python小试v1也保留负结果：SARA把提示中的来源ID当成运行时变量，Airline生成不在源文中的重复阈值直到8192上限。没有删除未执行代码或补写缺失return，见[原始小试结论](scalar_source_pilot_v1_results.json)。据此将程序生成与来源归因拆开，先只生成无来源ID的短程序，旧失败在静态未定义名回归中已拒绝；不沿同一失败方式批量发送。

程序生成与归因拆分后的[v2小试](scalar_source_pilot_v2_results.json)均完整并可执行：SARA当前题答对，但多个布尔判断直接写入，尚不能证明完整规则获取；Airline仅计算两件行李且费用错误。仍不批量复制失败源生成。另对48个开放Airline案例核实官方返回的base/size/weight中间量：按原包恢复行李顺序后，ticket＋逐袋(base＋max(size,weight))全部等于官方整数答案。该[核验](airline_native_component_audit.json)只确认可用的监督/诊断字段，不是源文AST金标，也不向预测器提供oracle。原始160 TEST未打开。
