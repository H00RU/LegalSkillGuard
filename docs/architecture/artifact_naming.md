# 现役工件命名

- runs/<run-id>/reports/skill_admission_round_XX.json：当前来源块全局playbook版本的五类硬门、直接发布结果、父版本与输出库。
- runs/<run-id>/reports/development_curve_point_XX.json：上一块全局playbook版本增量相对精确父库的下一块配对曲线；无版本变化时为库identity。
- runs/<run-id>/reports/library_effect_disposition_XX.json：联合增量的主指标、安全、暴露和区间诊断；有增量时固定为`observe_increment_continue_training`，无增量时为identity，不承担拒收或回滚。
- runs/<run-id>/manifests/teacher_round_XX.json：教师证据账本；除终端B8零预算外，每个健康块均进入累计证据，不存在“被拒库导致整块跳过”。
- runs/<run-id>/reports/learning_checkpoint_XX.json：输入/输出库、当前playbook版本增量、教师与机制统计的事务检查点。
- runs/<run-id>/reports/library_maintenance_XX.json：第2、4、6、8块整库静态、重复、冲突、领域与容量检查。
- runs/<run-id>/reports/final_training_holdout_arms_frozen.json：B8累计current、empty及可选exact-parent比较臂在增量诊断前的冻结绑定。
- runs/<run-id>/reports/final_training_holdout.json：最终累计库相对empty的同案诊断。
- runs/<run-id>/reports/final_training_holdout_disposition.json：累计库的全16端点开发诊断与干预隔离处置；性能非通过如实报告，只有干预污染阻止冻结/外测。
- runs/<run-id>/manifests/training_complete.json：完整128案和最终累计库冻结证明。

旧逐候选前瞻、跨块provisional/DEFER队列、单候选有/无技能分区及单块拒收恢复工件不是现役别名。现役只允许来源块发布的全局playbook版本在紧邻下一块作一次描述性测量；执行器发现旧schema拒收检查点会失败并要求全新run ID。
