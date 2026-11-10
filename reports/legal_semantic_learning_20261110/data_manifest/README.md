# NormBench 候选数据划分 v1

生成日期：2026-11-10。状态：已生成且通过自动检查，法源官方ID复核及64条分层人工抽检尚未完成。

- `normbench_candidate_split_v1.json`：256训练、64开发、128测试；每条包含source ID、临时family、目标span、原始数据哈希与仅供审计的机制字段。
- `normbench_quality_quarantine_v1.json`：132条 `rule_text` 不是归一化 `full_article_text` 子串的记录；排除发生在模型训练前，未依据任何模型成绩。
- `normbench_family_mapping_v1.json`：104个临时谱系组与原始法名映射；有98组进入三个划分。相关司法解释/前身法规的归组是保守审计规则，仍需核对官方标识。
- `normbench_reserve_candidates_v1.json`：70条备用；已分配家族的备用只准补入其原有划分，不得调往另一划分。
- `normbench_split_statistics_v1.json`：原始、质量过滤、全文去重、封顶池、各split的真实gold结构计数。

来源：[NormBench 官方仓库](https://github.com/AlexJJJChen/NormBench)，原始数据采用 CC BY 4.0；引用和署名请保留作者项目及对应[论文](https://arxiv.org/abs/2606.08932)。本目录增加临时家族映射、分层划分、哈希及质量筛选，不主张是原作者划分或重新专家标注。

冻结数据SHA256：`826bb2afb1b4ed5938043dc22802f22ac094df562e36acb9e348f52f928cfc19`。

已自动检查448条item、全文哈希、target哈希互不重复；family互斥；每family≤16；目标span全部可还原。`feature_strata_for_audit_only`、备用/质量标签、gold结构不得进入模型输入。模型输入只取原始记录的目标 `rule_text`、明确分隔的上下文及任务允许的原始元数据；目标外未标注内容不能计为漏节点。

现成监督可用于unit/branch/condition/effect提取、条件树、条件→branch以及effect→branch归属。`depends_on_units` 在中文数据中全为空；raw没有显式typed defeats/counterexception 图。论文另声明派生附着投影，但该独立投影尚未在本轮检查的main评测源码中定位/复现；派生深层例外数量未知，不是0个真实反例。AND/OR深度或重复排除叶数不能当成例外反例深度。

这是一份预先分层的机制研究候选集，不代表全部法条的自然分布。正式实验前只做既定质量抽检和错误类型修正；不按模型表现选题、换题或扩集。
