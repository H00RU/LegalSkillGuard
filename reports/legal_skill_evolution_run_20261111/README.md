# 法律技能进化：当前真实预检

Goal **active、未完成**。正在按固定20个TRAIN母来源推进独立获取和强对照；正式128来源训练、DEV及TEST尚未启动。当前没有两项方法成立的结论。

[唯一执行说明](../../docs/CURRENT_GOAL.md) · [当前证据与下一步](../../docs/METHOD_REDESIGN_CURRENT.md) · [逐请求、逐来源和成本快照](pilot_progress.json) · [快照生成脚本](update_pilot_report.py)

当前运行入口为 `experiments/legal_skill_evolution.py`，预检配置v7；冻结Qwen3-8B、thinking OFF，实际教师gpt-5.6-sol/high，不更新参数。19项相关回归通过，82个固定视图容量检查通过，最大直接输入7331 tokens，输出上限8192、上下文32768。

Full首批两个候选块包含四个真实教师程序，已通过编译和隔离执行接口检查。读取证据改为原文片段编号后，四个响应均完整结束，转述引用造成的拒绝消除；航空费用表字段及部分OE法源字段仍返回unknown，未进入APPLY，两个块均未接纳。Full首批累计60次逻辑候选—来源执行，包含一次明确接口修复后的30次回放。程序fixture、格式修复和fallback均不计核心成功。

已结算初答及负结果在v7零调用接续，失败字段及逐字支持交给后续更新。其他三臂独立真实获取、固定后续TRAIN队列继续；不原样重复Full首批，不补造unknown，不因普通模型错误停工。

**首条真实主路径结果来自强对照FreeEvolution/B1：** 接纳3个相互依赖的技能，在固定OE训练母来源上经真实读取、producer→consumer执行后，EC、EV官方F1均为1.0（初答来源均分约.07143）。这是训练反馈内的强对照成功，尚非跨来源验证，也不是Lift/CoRev增量；新建依赖包不可冒充学得共同修订模式。

[原始初答恢复规则](recover_original_B1_prefix.py) · [教师表示适配](recover_B1_teacher_ports.py) · [已结算首批接续](resume_after_B1_read_diagnosis.py)。全部原始wire、教师响应、版本表、源码快照及连续账本保存在既有artifacts，旧失败不覆盖。运行快照分别列物理请求、逻辑执行、缓存和tokens/time；订阅与GPU现金账单不可得处填null，不把本地API现金增量0写成总成本免费。

历史暴露核对仍在补齐：RR账本内当前TEST无请求；192个旧CNLI运行目录的原生结果与当前TEST/DEV无母文档交集，TRAIN交集7个；16个旧OE输入包与当前72来源无交集。这些是指定存储范围的结果，全历史冻结资格仍需最后汇总。

后续交付须包含真实Lift跨母来源绑定、学得CoRev模式对另一来源更新的作用、固定完整实验及强对照增量。当前小试和工程检查均不能替代这些证据；不进入论文写作。
