# 正式产物命名规范

本项目的活动产物使用“用途和语义”命名，不在文件名、目录名、数据集 ID 或案件 ID 中加入
迭代序号、阶段编号、临时批次编号或作者模型名称。正式数据集固定使用
`legal_skill_guard_dlawbench_style_cn`，案件固定使用`lsg_cn_XXXX`，相关清单、报告和测试统一以
`main_corpus`标识其用途。

模型名称、作者身份、构建日期、格式兼容性和冻结哈希应写入配置、provenance、manifest或报告
正文。`schema_version`仅表示机器格式兼容性，可以保留；它不用于区分内容优劣或实验先后。

后续主实验输出按实验语义、对照臂、随机种子和冻结哈希组织。需要保留历史时，将旧产物移出
活动入口并登记为历史审计材料，不通过给当前产物递增版本号来并存。配置和入口始终只指向一个
明确的正式产物集合。

## 当前主实验文件名

- `runs/<run-id>/reports/skill_admission_round_XX.json`：来源块候选的五类硬门、直接入库结果与输出库版本；不再沿用把“来源见证”误作完整准入含义的旧文件名。
- `runs/<run-id>/reports/development_curve_point_XX.json`：块首工作库相对匹配空库影子的prequential观察点。
- `runs/<run-id>/reports/learning_checkpoint_XX.json`：该块来源、入库数量、库规模与机制统计的累计学习检查点。
- `runs/<run-id>/reports/library_maintenance_XX.json`：第2、4、6、8块的整库静态合法性、精确去重、领域覆盖、容量与prequential绑定记录。
- `runs/<run-id>/manifests/training_batch_XX__complete.json`：绑定轨迹、评分、教师、准入、学习点、维护及输入/输出库哈希的块级事务完成标记。

旧`candidate_source_grounding_round_*`、单候选前瞻报告和`candidate_with/candidate_without`分区不是当前命名别名；新run不得读取或生成它们。
