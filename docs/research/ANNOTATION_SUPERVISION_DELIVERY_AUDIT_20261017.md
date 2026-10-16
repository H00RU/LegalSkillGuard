# 原标注、压缩与经验交付的实际审计

2026-10-17，anchored机制研究运行中。这里只使用已见18 TRAIN及已经完成的历史工件，
不读取本轮零散正确率，不修改389源码／418阶段冻结文件，不以此断言新表示有效。

## 已确认：不是本地重建混入了另一份数据

本地原包65362913 bytes、SHA256
`e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b`。
按Git blob格式计算的本地SHA1与官方发布文件对象
`757fd1dafd29a997fba00c60c6d40b2930a36159`一致。
[官方文件对象](https://api.github.com/repos/stanfordnlp/contract-nli/git/blobs/757fd1dafd29a997fba00c60c6d40b2930a36159)，
[官方项目](https://stanfordnlp.github.io/contract-nli/)。只打开TRAIN成员，423原案；未打开TEST。

383竞业／保密协议、430竞业协议、622服务／经销／竞业长协议就在官方原包中，最后一份
354个原SPAN。原论文附录对筛选范围的文字不能替代实际发布内容，更不能据此在观察
成绩后删掉困难合同。此核验未改变任何源文、分割、标签或批次。
机器收据：`artifacts/research/experience_faithfulness_20261017/fresh_official_zip_git_blob_identity_and_TRAIN_outlier_provenance.json`。

## 已确认的内容冲突：标注细节在压缩时没有保住

原TRAIN334／nda-18是E，Gold为[58,65,68]。新1371教师程序要求排除proxy solicitation，
但65是其standstill引言、68是proxy solicitation条款，二者都在Gold内。旧witness教师
甚至已逐成员解释，并对65明确要求作为benchmark辅助依据保留。因而至少在这个边界上，
不能说教师没见到Gold或不知道它指向何处；新的概括丢掉了已知例外。

若机械执行排除，只留下58，则该题依据F1为0.5，即便分类仍E。这是字面排除规则的
反事实计算，**不是**对正在运行的新学生答案评分，也不是认定原标注代表法律真理。

## 有明确实例的风险：读得懂的依据不等于完整法律证明闭包

原论文§2.1要求依据简洁、可理解，并找全重复依据；附录A.1.1描述按命题举例的标注及
覆盖优先的合并流程。它没有制定一个应无条件补齐所有背景法律前提的算法。
[原论文](https://aclanthology.org/2021.findings-emnlp.164.pdf)。

原TRAIN416／nda-10只标[12]，即协议存在／条款被视为保密信息的完整定义句；一般
保密义务另在13、14。新程序却要求经定义产生的保护同时引用定义与一般保密义务。
若无条件追加这些片段，会产生非Gold引用。这是可定位的目标粒度风险，不足以证明
学生一定如此执行、所有背景语都不该引用，或它是低F1的唯一原因。

详细原文与旧教师原解释在
`artifacts/research/experience_faithfulness_20261017/known_TRAIN_annotation_exclusion_and_evidence_granularity_semantic_audit.json`。
不得手工改这两个案件的Gold、为B4写例外，或改变正在运行的出版库。

## 经验信息确实少了一层，但尚不证明加回去有效

本轮教师收到的18个历史own观察包含199个非NM问题，其实际过去作答有31分类错误、
118联合错误、188个漏掉真成员、37个多选成员。20个入库示例中有6分类错误、10联合
错误、10个漏证和2个多选；runtime却只展开这些例子的正确Gold内容，没有展开实际
过去的错误选择及其成员级对照。334／nda-18过去分类已正确，仍漏65，而且未被选作
新runtime示例。以上是明确混合历史工具／库状态的观察，不是新库在训练集上的成绩。
机器全199逐题表：`artifacts/research/experience_faithfulness_20261017/past_member_feedback_distilled_out_of_runtime_examples_audit.json`。

只作容量研究：保持原4程序／scope／20引用不动，把过去实际选择与Gold证据的并集
逐片段标明observed_evidence、annotated_evidence，并保留两种原关系。旧Gold文本和
实际选择集合都可还原；这不包括完整过去文书、public reason或私有推理。
master3700／scoped3986，仍在4096内，0新生成／教师／fit。候选保存在
`artifacts/research/experience_faithfulness_20261017/unused_same20_past_correction_episode_capacity_candidate.json`，
**没有发布或启动**，不能自己修复未选择334的覆盖问题或错误程序。

下一动作由全部24原始答案的独立原集合复算决定：区分程序损害、仅示例收益、两者
互补、NM掩盖NN损害及真实证据增减，不按首案或一个总分决定。若需要改学习表示，
须改变信息保留／可执行工作单元等真实环节，而不是以更多泛泛提醒替代它。
当前原任务、冻结8B、未调优官方TEST及完整论文目标保持不变。

## 07:11补充：实际纠错库的上下文与结论边界仍需检验

上述anchored24已完整负面收束；corrective Run01已用原24已见案及真实own答案更新
最新父库，四UPDATE／4条、16例，正后台完成后续8开发合同的16个配对答案。不得将
历史容量候选或内容纠正本身报成新案收益，当前未评分该研究的零散答案。

实际选中的唯一NM局部反例是334／nda-16。律师过去误选37、40、41、46；runtime
忠实展开这四片段，但没有39的“Promptly upon the Disclosing Party’s request”触发语。
教师程序正是在区分request-only与termination-trigger，关键辨别上下文却未随例交付。
这是具体的源上下文丢失；不证明未来律师一定误用。原NM没有Gold依据集合，不能把
未标成员直接解释成脱离条件仍无关的法律负例。收据在新run的
`monitoring/past_only_negative_context_and_annotation_sufficiency_scope_audit.json`。

同一收据另记334／nda-18的风险：原文同时有雇员招揽限制58和proxy限制65／68。
必须保住原Gold成员，但这不足以推出proxy限制**单独**就支持representatives命题。
证据成员关系、可读上下文与足以成立分类的条件应分清；不能用一种粗粒度“正例”
替代三者。这是新程序适用边界风险，而非已观察到的未来错误或原Gold错误结论。

不热改474冻结绑定、不加逐案例外、不选回旧高分库。先收齐原定16答，按原集合
分解真实得失，再决定是否需要在经验表示中保留辨别所需的完整条款上下文。
