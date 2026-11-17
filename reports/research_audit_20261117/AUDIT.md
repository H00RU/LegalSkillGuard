# 源码与原始证据复核

日期2026-11-17；对象为1f132108fa326d46118c3c708458fbbafec7bfb2。

## 一、核查范围

依据两个manifest下载并校验174个文件，哈希全部一致。阅读`program_residual.py`、`asset_port_decoder_v2.py`、`production_decode.py`、`m1_feasibility_attribution.py`及有限包原始数据，执行本包`audit_packet.py`。未调用研究模型，未修改服务器，不打开新的DEV/TEST。

完整离线复现命令在本机Windows/Python3.10导入Linux专用`fcntl`时停止。本报告没有声称独立重现服务器全部57/29等检查；服务器报告的全链复现与本轮脚本的原始请求检查严格分开。包中要求Python3.11和若干固定依赖，本机没有伪造依赖或跳过生产验证冒充通过。

## 二、新发现：原生题目的任务假设没有完整进入读取请求

本轮查看18个案例（3个TRAIN母来源×两个视图×三种布局，不是18个独立来源）：原生`native_views.*.public.original_input`全部包含夫妻共同所有、等份权益的默认条件，并规定除非明确另有说明；读取请求只携带个人使用默认条件。原始请求中逐项检索和人工阅读都未见共同所有假设的对应完整传递。

脚本结果：18/18个案例有原生共同所有默认句、读取请求没有该默认句；个人使用默认句18/18均保留。字面检查本身不证明不存在任何同义表达，故另人工核对争议来源的完整system/user内容和`public_task_context`，确认该处只列个人使用默认。

争议字段`asset_is_personal_nonbusiness_property`的提示定义同时涉及个人/商业用途与债务人所有权。源审对义肢的“claims ownership”与“a disclosure reports”保留unknown，而模型回答true；但原生任务提供的默认条件必须先纳入字段解释。参考不是独立司法事实金标。

**能下的结论：存在真实的信息传递不完整与字段语义混合问题，参考unknown与模型true不一致，不足以单独判定模型补造事实。不能下的结论：所有true都正确，或应把参考unknown全改true。** 共同所有默认有触发条件、主体条件和明确反例优先，需按官方任务而不是按诊断标签解释。不能把个人使用自动等同所有权。

建议拆开`ownership_status`、`use_purpose`、`legal_category`，分别保留事实、任务授权假设、法条分类推论的来源。这个建议是任务契约修复，不计方法贡献。

## 三、实际自动改写是什么

[program_residual.py](https://github.com/H00RU/LegalSkillGuard/blob/1f132108fa326d46118c3c708458fbbafec7bfb2/legal_skill_guard/paired_interfaces/program_residual.py#L63)：`specialize`将声明的公开上下文字段替换成常量；`closed_value`求值封闭布尔/比较表达式；`visit_If`裁剪分支；剩余静态输入字段形成端口。证书本身写明是`static_context_substitution_and_closed_branch_pruning_v1`。

这是实际程序改写，不是手工换名字；但目前该核心是部分求值/常量传播/死分支消除。不能单凭自动化就认定独立新算法。Airline重量等价类也应与有限域最小分类/区间编码比较。旧方案中更丰富的关系绑定、联合残差合成，不能用这些已实现操作代表。

## 四、分数与归因

从封存逐行评分重新计算：M1四个诊断任务均分1/3，固定接口和普通提示选择均0；三臂完整正确均0/4。本轮只复算存储的分数，不宣称重新运行原生评分器。

[归因代码](https://github.com/H00RU/LegalSkillGuard/blob/1f132108fa326d46118c3c708458fbbafec7bfb2/experiments/m1_feasibility_attribution.py#L51)把参考unknown、实际stated/negated登记为差异，并检查正分行均关联该差异。这能证明与参考不一致，不能独立证明参考是正确的任务解释。服务器最终报告也要求对齐官方任务假设；此处需要落实，而不是把unknown审核当作不可修改的法律真值。

固定F覆盖不全、MAUD输入片段缺失、输出拒绝是另外的问题。修复全部问题也不会自动证明M1有独有收益，必须给所有对照同样修复。

## 五、M2决定

保留停止当前M2的结论：无约束未知质量导致相同最坏风险；训练观察相容的跨结构通道可给出相反排序；在假设平稳的构造例子上，联合差分迁移也能复现选择。不能靠增加真实调用、成本打平、删unknown解决独立贡献问题。

本次没有独立重跑M2全套代码；该段依据已发布M2两关报告，不能与本轮M1原始请求实查混称。

## 六、评估结论

旧M2：Reject and Pivot，停止此版本。旧M1作为已成立独立贡献：不批准；作为可复用编译工程资产：保留。两项替代方法：本轮尚无可以批准的组合，不给虚构五维高分或Strong Accept。

最重要的修正是：之前把接口优化包装成创新时遗漏PARSE；把参考unknown与模型true差异过快解释成忠实性失败。两项都应更正，但它们不能互相抵消后得出“方案恢复可训练”。

## 七、复核命令

```text
python audit_packet.py /path/to/M1_finite_evidence_20261117/finite_replay.json.gz
```

脚本锁定原始包SHA256，只读TRAIN包，报告假设传递、来源数量和封存分数算术。没有调用网络、模型或教师。
