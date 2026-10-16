# 已核实的执行／经验交付差异：下一动作的证据，而非效果结论

2026-10-17，support/refute诊断后台运行期间记录。没有修改该诊断398个冻结绑定，
没有查看其新答案正确率，没有启动第二个GPU任务或新教师。

## 当前已完成实验给出的约束

固定普通M2的两次真实原生反馈修订已完成，最新17条库无条件使用；B4技能相较同工具
无技能仅多1个分类正确、少1个联合全对，真依据3增7丢，F1由69.23降至63.29。
不能继续以“教师未拿到Gold／真实答案”解释：它拿到全部18已见原案和原标注，以及
自己的真实父库／草案作答。查询覆盖改善也没有自然转化为最终选证改善。

所有7个丢失真依据均在Gold C、最终NM的问题：5个原先分类正确，2个原先错E但取到真证。
因此当前12新答／0教师的诊断只检验原生支持／反驳判定执行，不证明学习已经修好。
两个判定由律师生成，原始choice直接评分，不作host语义判定／生成后翻标签。

还有29个未获取的原标注成员不在两类候选池中，分布在21个问题。逐条原文已读；
包括独立限制条款、列表引言和跨段限定语。不能靠强制选候选、自动相邻并集或只修NM
解决；先前直接并集／邻居／literal重复／稠密全集输出失败记录保留，不重新包装为新招。
完整源和逐集合收据：
`artifacts/research/experience_faithfulness_20261017/completed_old_B4_all29_acquisition_misses_and18_source_class_coverage.json`。

前18 TRAIN的306原判断为E168／C31／NM107；17命题中11个未出现C，nda-11全18为NM。
这只描述这18份合同的覆盖，**不是**原数据集整体分布、数据不适合、应人工改标注，
或“补齐三类一定有效”的证据。有些命题本来就很少出现某类。当前17条规则的跨类
边界不能仅以已给全标签就当作验证充分。正式TEST仍未用于调优。

## 实际作者代码，而不只是论文标题

1. ExpeL官方`agent/expel.py`，固定commit
   `e41ec9a24823e7b560c561ab191441b56d9bcefc`，实际743行，SHA256
   `7db4e1be3c16dfca589eb2e194cfb4604be224dab32a04f7f03c4529b1dfcf74`。
   `insert_before_task_prompt`插入提炼规则；`setup_vectorstore`构造成功轨迹库；
   `update_dynamic_prompt_components`将检索到的历史任务及完整选定轨迹写入fewshots。
   它排除当前同任务并限制示例长度。只借其规则更新操作，不能称复现了完整ExpeL。
   [固定作者源码](https://raw.githubusercontent.com/LeapLabTHU/ExpeL/e41ec9a24823e7b560c561ab191441b56d9bcefc/agent/expel.py)。

2. 《Large Language Model Agents Are Not Always Faithful Self-Evolvers》采用
   原始经验／凝练经验的干预区分“有记忆块”与“实际利用内容”，报告二者利用的差异。
   这支持检查经验交付，不证明我们的瓶颈或新方法一定奏效。读的是
   [v3，2026-06-12](https://arxiv.org/html/2601.22436v3)，不是截至10月17日最近三个月新论文；
   早期v2的10个backbones不要与v3／README的13个混写。没有把其模型分数移用到法律。

3. 上述研究作者代码固定commit`cc8c37da02896bb935233dec6990177a5124a923`
   （2026-05-29），`ExpeL/agent/expel.py`实际1167行，SHA256
   `d59791e07efe9a0f94da5d56d610dc64d9d74f89d42791527ef8d0fcf243d89c`。
   已读规则插入、示例检索及`_modify_fewshot_for_faithfulness`／
   `_modify_insights_for_faithfulness`。作者实际`empty`分支分别返回空串／空规则列表；
   不保证整个prompt长度、所有格式或算力严格匹配，不能只引用README就声称匹配。
   [固定干预源码](https://raw.githubusercontent.com/Dreamcatcher0622/Faithfulness/cc8c37da02896bb935233dec6990177a5124a923/ExpeL/agent/expel.py)。

仅阅读公开源码并保留URL／SHA，没有复制、安装、运行外部代码，没有下载模型，
没有采用其失败重试、长上下文fallback、额外embedder或另一套推理服务。
机器来源收据为`artifacts/research/experience_faithfulness_20261017/primary_code_provenance.json`。

## 本项目确实不同的地方

当前运行库只有inspection与source_queries。此前witness方案虽然要求教师逐Gold成员
说明，但`learning/witness_grounding.py:publish_with_training_witnesses`在发布前明确
pop掉training_evidence_accounts及每次编辑的witness_checks，律师没有拿到这些具体示例。
这不是遗漏传参，而是当时有意的抽象／去个案设计；已有失败事实说明它不保证弱律师
能够重新推导所有细节。literal候选是**当前合同**原文，不是**过往合同**的已标注示范；
typed branch是抽象条件及关系，不是源例。两种机制不可冒充同一个已验证实验。

对当前生产代码、config和run协议的fewshot／exemplar／demonstration搜索没有找到
一个完整的历史源证据示例交付链；review.py反而明确禁用demonstrations。
此结论限定于本次重建后可检查的代码／实验，不能断言9月27日以来从未试过任何例子。

## 当前诊断之后的动作边界

先取齐12次并独立重数四格。若只是两臂一起改善或技能仍负收益，不把通用格式改进
冒充技能进化，更不以此启动同配置正式长训练。

若需继续改变经验表示，优先检验**可追溯历史依据示例与可迁移程序共同交付**，而非
继续只让教师重写抽象提醒／同义词。候选应由原教师基于已见原TRAIN和实际错误生成，
不手编B4规则；示例仅来自过去原Gold，完整交付所选例子的原标注依据，并与当前源明确
区分坐标和身份。未完整提供历史文档时，局部摘录不能作为整案NM的证明。

这仍是未实施的候选，不是成功结论或新正式主方法。需要与同样示例但无程序、程序但
无示例及强空库区分；保留4096总记忆预算、冻结8B及原任务，所有最终判断仍由律师做。
不能把单纯few-shot检索的收益改称技能贡献；正式论文仍需完整跨批学习、公平成熟
方法、独立重复、真实成本及未调优TEST，不以这份研究记录替代。
