# 当前候选与已有方法的实现边界

2026-10-15代码核对；不是新增基线结果，不向运行中的实验注入新模块。
保留旧成功补丁恢复出的ExpeL适配代码及协议在独立恢复归档，不重新猜造旧库或旧答案。

## ExpeL

核对[作者代码](https://github.com/LeapLabTHU/ExpeL/blob/e41ec9a24823e7b560c561ab191441b56d9bcefc/agent/expel.py)，
commit `e41ec9a24823e7b560c561ab191441b56d9bcefc`；实际下载文件SHA256
`7db4e1be3c16dfca589eb2e194cfb4604be224dab32a04f7f03c4529b1dfcf74`。
规则计数器按REMOVE、AGREE、EDIT、ADD的顺序处理，ADD初始2，AGREE/EDIT加1，
REMOVE减1（列表满时减3），计数不正者移除，按计数排序；不是简单只追加规则。
作者还从同任务成功/失败轨迹对比及成功轨迹组抽取规则，并检索实际成功示例。

历史成功补丁已恢复相同commit与文件哈希的expel_rule_kernel.py，以及后来修正的
expel_numbered_success_adapter.py：短编号全局规则、按完整来源无损归并真实成功命题，
不再让律师重复数百个长ID，也不把一个成功组件冒充整份17题成功。
该适配使用过去数据拟合的TF-IDF而不是作者MPNet，并含组件success、按批及标签辅助的变化；
未来只能明确称法律适配，不能冒称canonical复现或我们新发明的计数器。
对实际下载的固定commit源码做AST比较，retrieve_rule_index、is_existing_rule、update_rules
三个恢复函数均逐AST一致；这不等于整个法律适配已经忠实复现或取得新成绩。
恢复代码仍位于forensics/reconstruction/success_events_v2/temporary/
legal-clause-inspection-20261013.amOq7f，不作为未使用依赖堆进当前生产包。

## ReMe

先核对[正式论文记录](https://aclanthology.org/2026.findings-acl.829/)，再找其旧程序记忆版本，
而不是将当前个人知识库README当成论文算法。
作者README所指旧标签v0.2.0.6实际commit为`554eec1cb94821212c8b81d5499c9e7f42de5c16`。

- [comparative_extraction_op.py](https://github.com/agentscope-ai/ReMe/blob/554eec1cb94821212c8b81d5499c9e7f42de5c16/reme_ai/summary/task/comparative_extraction_op.py)：
  软比较仅在最高分大于最低分时执行；相似成功/失败步骤比较默认另行关闭。
  提取的TaskMemory分开保存when_to_use和experience；不是仅增加一段无条件提醒。
  文件SHA256 `b8ded7001480bc7e1187372ad5ac0e6f0d8660958132988242e21679f4a4dde9`。
- [failure_extraction_op.py](https://github.com/agentscope-ai/ReMe/blob/554eec1cb94821212c8b81d5499c9e7f42de5c16/reme_ai/summary/task/failure_extraction_op.py)：
  失败本身可以提取记忆，不要求必须拥有一条成功轨迹才准学习。
  文件SHA256 `07da8ecb76d1558fe7856dd403fc3bd7b6205a13c4f2d092306a181f19a77b56`。
- [update_memory_utility_op.py](https://github.com/agentscope-ai/ReMe/blob/554eec1cb94821212c8b81d5499c9e7f42de5c16/reme_ai/vector_store/update_memory_utility_op.py)：
  此文件在上游标记update_utility时给现有utility加1，本身不证明正确判定了记忆贡献。
  文件SHA256 `ceaeebbfceabbbb84c4914334b8c86f8fe69b5b92e10747d1c0d8e428b3fb691`。

当前四批候选不是ReMe复现，也没有重新加入k=4或组内择优。
参考代码说明失败定位、条件化经验和非追加更新值得核对；不能据此推定这些模块必然解决
ContractNLI的完整依据识别，更不能把尚未跑的新基线成绩写进论文。

## 下一步的约束

先完成已冻结的真实四批与新案对照；只有效果证据支持才选定完整方法比较。
公平主比较仍欠任务盲静态、同源无轨迹、忠实标明适配的ACE/ExpeL和独立学习重复。
不靠弱化基线、把原始示例组件遗失掉、忽略接口空库差异或隐藏真实成本来制造优势。
