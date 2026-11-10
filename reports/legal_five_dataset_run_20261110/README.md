# 五库混合学习当前执行证据

当前Goal继续，依据[统一方案](../legal_five_dataset_amendment_20261110/PLAN.md)及唯一[当前执行说明](../../docs/CURRENT_GOAL.md)。本报告原位更新，不构成新的目标或调用队列。

已核验256 TRAIN/80 DEV/160 TEST身份；TRAIN为NormBench128及其余四库各32，合同恢复全部17假设。四旧库原始公共输入hash一致，ProofWriter开放48来源的参考Horn闭包与原生答案一致；Airline参考评分只在开放TRAIN/DEV侧执行。没有新打开TEST文本或标签。旧DEV每库8来源已有开发暴露，明确保留为开发，不声称盲测；固定TEST候选未在当前实际请求账本中发现调用或oracle暴露，仍待下一阶段授权。

NormBench保留指定128 TRAIN不变；按直接司法解释谱系合并，3 DEV与5 TEST身份从原同名分区的未选条目替换，未按模型成绩筛选。详见[谱系修正](lineage_reconciliation.json)。原始候选及全部历史清单未覆盖。

[原生适配核验](native_adapter_audit.json)和[token长度核验](native_tokenization_audit.json)记录实际字段及掩码。训练源最大8818 tokens，没有截断。ContractNLI17接口使用明确记录的运行时格式：已核对旧文档hash与官方全部17假设/证据，另存新输入hash；未将未公布序列化方式的桌面17任务hash冒充已复现。

共享内容/来源视图、原生节点、普通组合与定向四格实现继续复用；新增M1局部信用及MML/HardEM/执行过滤目标已接入独立模块，必要梯度回归通过。它们目前是代码与离线回归，不能计作真实方法收益。共同原生初始化已完成：256来源（Norm128、其余各32）全部记录非零来源梯度，32次优化器更新，耗时473.187秒，训练43,646,976个LoRA参数；原始8B权重未更新。全部七系统将从这一相同初始化继续固定三轮混合训练。权重哈希见[共同权重清单](common_weight_manifest.json)，曲线见[实际优化步](common_optimizer_steps.jsonl)。

随后5条真实TRAIN原生推断均EOS结束、无截断，初始执行账本1410→1415、教师仍74；两轮定点复核另计4次，当前1419E/74T。它们不是DEV：SARA这一条答对，合同11/17，Airline这一条错误；Norm返回未定义中文规范类别，ProofWriter返回了错位原子格式和缺括号。完整[原始输出](common_native_smoke.json)、[逐来源审计](common_native_smoke_audit.json)及[请求账本差量](common_request_ledger_delta.json)保留。不能以4/5 JSON可解析冒充语义通过。已据真实问题补明枚举/原子示例，并为所有比较共用原生JSON grammar；256 TRAIN目标通过schema检查，五个grammar均已在本地xgrammar编译通过，第二次真实复核暴露了后端Unicode枚举乱码与ProofWriter重复规则循环，未批量追加同一失败请求；原始结果见[v2复核](native_schema_v2_results.json)。进一步以可逆ASCII角色码和公开事实/规则列表上界修复，全部TRAIN目标及五库实际目标token＋EOS通过grammar回归。[v3真实复核](native_schema_v3_results.json)两项均正常结束、通过类型和执行：ProofWriter闭包为Unknown，与原生TRAIN答案一致；Norm可执行但跨度F1仅0.2353、整图错误。它们只定位工程主路径，不能充当M1/M2收益或整体训练就绪结论。原共同初始化保留，不按失败样本补造语义或重复初始化。

尚未完成：方法专属三轮训练、源候选与原生执行表、M1非Norm机制结果、M2实际使用、七系统曲线/逐来源DEV结果与阶段复核。Goal保持active，不以本次报告或准备状态结项。TEST与论文未启动。

实际标准Python小试v1也保留负结果：SARA把提示中的来源ID当成运行时变量，Airline生成不在源文中的重复阈值直到8192上限。没有删除未执行代码或补写缺失return，见[原始小试结论](scalar_source_pilot_v1_results.json)。据此将程序生成与来源归因拆开，先只生成无来源ID的短程序，旧失败在静态未定义名回归中已拒绝；不沿同一失败方式批量发送。

程序生成与归因拆分后的[v2小试](scalar_source_pilot_v2_results.json)均完整并可执行：SARA当前题答对，但多个布尔判断直接写入，尚不能证明完整规则获取；Airline仅计算两件行李且费用错误。仍不批量复制失败源生成。另对48个开放Airline案例核实官方返回的base/size/weight中间量：按原包恢复行李顺序后，ticket＋逐袋(base＋max(size,weight))全部等于官方整数答案。该[核验](airline_native_component_audit.json)只确认可用的监督/诊断字段，不是源文AST金标，也不向预测器提供oracle。原始160 TEST未打开。
