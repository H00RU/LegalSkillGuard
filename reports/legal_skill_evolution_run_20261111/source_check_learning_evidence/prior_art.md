# 定向近邻及实际借鉴边界

2026-11-13。本轮没有重新全量检索。以下条目基于已有定向原文/官方代码核查，按具体版本记录；没有运行这些项目，也没有取得其测试材料修补本项目。

|工作与原文|核对的实际机制|与当前实例的关系|
|---|---|---|
|[ProcMEM v1](https://arxiv.org/html/2602.01869v1)，后续[Skill-Pro v3](https://arxiv.org/html/2602.01869v3)|过程诊断、semantic gradient、候选技能及likelihood准入|可借鉴实际过程更新；不是法律原文真值认证。版本不混用|
|[VeriSkill v1](https://arxiv.org/html/2607.27733v1)|形式验证责任归因、lesson抽象、局部执行验证|验证oracle/人工reference条件不同；本轮检索未定位官方实现，不声称不存在|
|[CoEvoSkills v1](https://arxiv.org/html/2604.01687v1)|技能与独立surrogate测试共同演化，opaque oracle反馈|“独立critic+持久化测试”已有近邻；不能单独当差异|
|[GenV v2](https://arxiv.org/html/2609.11085v2)|区分verdict保持与formalization语义保持；相对指定gold用Z3等价|支持答案相同不等于形式化正确；不能移植gold oracle假设。其LoRA不是当前冻结模型方案|
|[By Their Fruits v2](https://arxiv.org/html/2605.25186v2)|形式化匹配与SAT/XOR边界问题|参考形式等价不等于自然源意图的自动真值|
|[GDPR autoformalization v1](https://arxiv.org/html/2604.14607v1)|法律范围、角色/例外评审及人工复核|法律judge有直接近邻；不能把固定judge宣称为学得策略|

官方实现核查：

- Skill-Pro固定提交 `3be7a9be2d4c024d132efe394d537404eba7e4c8`：[skill_evolution.py](https://github.com/Miracle1207/Skill-Pro/blob/3be7a9be2d4c024d132efe394d537404eba7e4c8/Skills/skill_evolution.py)、[loss.py](https://github.com/Miracle1207/Skill-Pro/blob/3be7a9be2d4c024d132efe394d537404eba7e4c8/Skills/loss.py)。实际重算历史动作logprob，不是模型反传。本文没有声称忠实复现NP-PPO。
- CoEvoSkills固定提交 `4380d4bff673dd6e1d58e5babeb2aaa0fe527119`：[independent_verifier.py](https://github.com/Zhang-Henry/CoEvoSkills/blob/4380d4bff673dd6e1d58e5babeb2aaa0fe527119/libs/terminus_agent/evolution/independent_verifier.py)。核对独立会话、继承测试与脚本错误/输出错误的区分。

实施决定：本轮确实学习检查问题、取证程序和排除映射，再用真实执行筛选；成熟子集搜索不算新求解器。源语义检查仍会误判，因此误删、unknown、重读和最终规则全部计入。固定强对照没有显示增量，本实例关闭，不通过换名或论文叙事把它写成已成立贡献。
