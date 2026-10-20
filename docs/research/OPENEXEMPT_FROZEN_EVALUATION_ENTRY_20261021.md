# 冻结库最终评测入口，当前未对封存数据执行

`experiments/openexempt_frozen_eval.py`只复用现有Online/ACE作答方法、原生评分和
源码/双盘保全函数。它不是新学习器、额外LLM层或验证集，不修改技能或模型。
本入口在2026-10-21开发，仅用合成CPU样例检查，没有加载封存TEST题面或标签。

## 实际启动条件

必须先完成主方法、对照、学习重复和必要消融，固定全部末库与统计方案。
再填写完整比较配置，令evaluation_role为sealed_frozen_comparison、
final_matrix_frozen为true、no_validation_set为true；配置不允许teacher字段。
当前没有可运行的最终比较配置，不能把入口实现或合成测试通过称为实验完成。

配置沿用现有generation、inference_environment、upstream_archive、protocol、
input_packet、grading_directory。source_cases为完整TEST来源数。
training_source_cases、training_batch_source_cases、training_packet_sha256固定共同
TRAIN数据与批次。statistics_plan必须指向已明确写好的、在预测前固定的统计方案。
当前IID128预案不等于已完成该最终统计方案。

每个arm有name、role、backend；reference_arm必须是唯一strong_empty。
其余arm列出source_config、source_config_sha256、bank_sha256，不能内联一份
手工改写或挑出来的好库。所需role及实际取库方式：

| role | backend | 实际库 |
|---|---|---|
| strong_empty | direct | 空库，不引用学习配置 |
| evolved | direct | 完整学习结束时的末次发布 |
| B1_frozen | direct | 对应同一次完整学习的B1发布 |
| experience | ace | 完整ACE学习的末次原生playbook |
| ablation | direct | 完整消融学习的末次发布 |

每份持续进化库须有其自己的B1冻结控制。学习状态、批数、EC/EV实际来源总数、
共同数据与接口版本均核对；32案ACE13或未完成学习不能冒充128案ACE14。
推理使用与学习相同的共享任务接口，ACE还须保持其实际学习时的Generator适配。
因此未来0366e9a类型修正必须先整合、训练对应ACE，再评测，不能到TEST时才改它。
同一个学习Run ID改几个名字不算独立重复，入口会拒绝这种重复声明。

从项目根目录运行，且与训练共用唯一锁，不抢占模型：

```
python -m experiments.openexempt_frozen_eval freeze <已完成的最终比较配置>
python -m experiments.openexempt_frozen_eval run <同一配置>
```

freeze复用现有源码/data字节hash和双盘保全；字节hash不是人工查看题目或答案。
run核对冻结矩阵后先记录evaluation_started，再读取完整公共题面。该标记之后
不得据其表现继续调方法并仍声称本集从未暴露。

## 执行与结果边界

全部arm、全部来源的首答均保存后，才统一打开标签评分。输出原EC/EV宏F1、
完整EV与额外声明等原记录，以及同案相对强空库、相对本次B1库的配对差值。
精确相同的原始请求只复用同一响应，明确不算独立生成，实报物理调用和token。
协议/输运失败保留并停止；不能选另一答案、修答案、删题或换seed补齐好结果。
空答案、格式失败、截断等沿用现有原评分路径，不替换成重答成绩。

入口计算逐来源评分与配对点差，不自动宣称显著性、算法稳定性或重复训练独立。
置信区间、多重比较与学习重复变异必须按已固定统计方案另行计算，并保留来源
级EC/EV配对关系。不能用同库重复解码代替独立学习重复，也不把benchmark标签
一致性当作真实法律建议正确性。

师兄paper-experiments-appendix用于确保完整对照、原始成本和证据强度。
当前仍须取得修复版128案真实收益、成熟同条件对照及独立重复，才可开启最终TEST。
