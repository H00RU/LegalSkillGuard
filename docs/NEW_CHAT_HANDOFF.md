# 交接：从当前Goal的未完成处继续

2026-11-18。先读 `docs/CURRENT_GOAL.md`，再读固定统一方案 `reports/legal_skill_convergence_20261117/PLAN.md`、METHOD_1、METHOD_2、protocol和REVISION_REVIEW。此交接不新建Goal、不启动另一研究方向。

## 恢复工作前必须核实

1. 调用get_goal核实当前完整目标及active状态；用户新授权覆盖旧维护任务和旧方案的停止执行范围，不恢复历史队列。
2. 检查实际研究进程、工具会话、服务、账本reserved和当前代码绑定；PID、进度文件或意图本身不足以认定任务live。live则观察同一任务，不重复启动；失效则核对账本和终态，从未完成处恢复。
3. 核对Git分支/修改，保留全部未提交资产；读取 `artifacts/legal_skill_convergence_20261117/handoff/` 的最新回执/运行状态。
4. 复用有效响应；精确wire、来源和模型版本不匹配时不得当新版本独立证据。失败请求仍计费，不隐式重试。

## 当前状态（需恢复时再验证）

固定方案上游37a76ffdf9490d7d213f5a9e67553a174416d84c已完整导入43文件并逐Git blob核验；工具会话29249和70214均exit0。未启动研究driver。Qwen服务PID536850/537626已在本轮只读检查中确认live，thinking要求关闭。累计账本12427/reserved0，新Goal研究请求0。原177源审、全部旧结果/源码快照和曝光记录保留。

M1关系合成/实体绑定/源忠实性和新M2共享解释/依赖闭包/跨组持久化均已有实现；生产InterfaceActor和decode_response已支持来源绑定的关系接口。45项离线检查已通过，包含旧18份付费响应回归；不能当成新模型效果，也不要重跑同一检查。真实五库provider、实际读者候选选择/持久化技能复用、M2真实来源独立K与教师更新闭环尚未完成。

Diversity固定24个TRAIN及独立参考核验24/24×3字段已准备；128个TRAIN/8批候选、旧4库非TRAIN DEV64、隔离的4库新TEST候选128已存档。只读 `handoff/source_metadata_current.json` 和 `handoff/diversity_train_current.json` 获取版本；**不要打开 `sealed_test_candidate/public.json`**，不要将待完成的分组/近重复核查写成最终盲测成立。Diversity DEV16/TEST32已隔离准备，CNI17任务已规范，见 `handoff/normalized_inputs_current.json`；总数据锁定及MAUD未扩展excerpt的覆盖核验待完成。

下一动作是固定Diversity官方公共语义/查询与版本，隔离准备剩余分区，规范CNI/MAUD；并完成两机制真实学习闭环。先锁定来源/指标/共同初始化与预算，再执行结构选择的20例小试；不要重跑旧pilot、旧M2拟合或旧教师96任务。新Goal实现尚未公开提交，需尽快沿已授权研究分支同步，排除密钥、整库账本和隔离TEST内容。

## 必须保留的历史边界

旧M1小试columns全零与后续有限OE结果（原生F1=1/3但完整正确0/4、源审unknown→true）是失败证据。旧M2上界全1和两关未通过是失败证据。不能通过费用打平或降低unknown强行制造选择有效。新统一方案应正面解决已知原因，科学效果未成立前不称两项贡献已获支持。

原DEV/TEST已有曝光，SARA完整未暴露库存曾为0；新方案测试安排需按来源事实实施，不能将旧题改名为新盲测。完整训练/曲线/独立消融/强对照/冻结评价/论文和可靠归因证据尚未交付。只更新报告或离线通过不达成Goal。

最新接手回执：`artifacts/legal_skill_convergence_20261117/handoff/goal_activation_receipt_20261118.json`。旧完整交接已归档于 `docs/history/before_convergence_goal_20261118/`，不继续累加矛盾状态段落。
