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

## 07:23完整后续8案：有联合收益，取证瓶颈仍未解决

corrective16／1已完整结束并独立按原作者TRAIN集合重算：技能准确率83.09／F166.67／
joint60.29%，同工具无技能82.35／67.26／55.88%。标签11修10伤，联合12修6伤；
非NM联合净+2、NM净+4，但真query-SPAN6增8丢，仍未达全部目标。8个丢真全部随
答案变NM，其中4个在普通候选里已可见。6个增真里5个是NM恢复非NM，仅1个是既有
非NM答案的额外成员。不能把联合+4.41pp包装为证据获取突破。

实际失配包括：327明确request-only仍被答E，374全部返还无保留却答NM，341无论
是否标记的定义已是候选却答NM，270把禁令救济误当survival；相应规则都已经写出。
这些公共答案与实际出版内容的不一致证明执行未可靠对齐，但不证明单一心理因果。
624的whether-or-not-written原Gold又暴露“要求显式oral/verbal”把充分线索收窄成
必要条件的问题。严格保护Gold成员仍不保证可迁移程序没有错误排除，或者弱模型
能够从局部对照恢复正确的NLI关系。

全26变化题、原Gold/实际选择全文、8合同逐案指标、来源bootstrap及实际wire审计
保存在新run monitoring/complete16_original_author_manual_sets_paired_changes_actual_wires_and_source_uncertainty_audit.json；
内容／执行／候选分解见同目录complete16_actual_NM_collapse_candidate_visibility_rule_execution_and_content_scope_root_audit.json。
当前仍不是独立重复、公平成熟方法比较、强空库或正式TEST，不修改不利结果。

## 08:13只读补充：存储容量与调用上下文、旧试验范围

contextual Run03的实际新库已把完整416源及10个原命题答案送入律师输入，不再只是
编译候选。此处未查看本轮零散质量、未改变559冻结绑定，也未生成新资格答案。
原32已见案仍在档案与catalogue；实际runtime只选择1案、覆盖10/17命题，每个所选
命题只有1种过去原关系。nda-1原32案为E6/C8/NM18，runtime仅示范E。它不证明
所有命题都应覆盖3类、需要硬性配额，或未来答案一定受损。

保持实际4条inspection及scope不动，仅做无生成的容量计算：无示范scoped892；
nda-1源文成本最低的E案290单独示范2142，C案270单独3121，而把这两份完整源
一起示范为4373，超过4096。此数字只证明这个具体组合在当前程序文本下超预算，
不是所有组合的全局最优证明，也不是选出一个更高分库。当前“全库全部展开都须4k”
把保留经验量与单次上下文绑定；若跨批证据仍不足，可研究把经验池与实际检索上下文
分开，但不能仅凭容量认定检索有效或给它增加模型/裁判。数据与未发布容量视图在
`monitoring/past_only_global_capacity_vs_served_context_and_relation_coverage_audit.json`。

实际作者ExpeL代码的setup_vectorstore保留成功轨迹池，另有rule_items规则；
update_dynamic_prompt_components检索完整任务/轨迹，限制示例长度并排除同任务。
这是独立于全池存储量的提示选择机制，不等于我们当前静态展开；未声称复现整个方法。
[固定作者源码](https://raw.githubusercontent.com/LeapLabTHU/ExpeL/e41ec9a24823e7b560c561ab191441b56d9bcefc/agent/expel.py)。

另用不受gitignore影响的文件遍历读1699份旧ContractNLI原生请求（不含本次运行）：
本轮16预选案与这些旧调用的交集为空。1608份是choice/spans/reason/usedIDs，24份
去掉usedIDs，18份checks在choice前，20份support/refute在choice前，24份applied_branch
在choice前；这些稀疏每题接口中都没有发现spans先于choice。5份非这种接口另计。
实际读旧sourcewise代码，要求给所有SPAN显式归属，是稠密输出而非同四字段稀疏换序。
旧备注声称“输出排序已有负面”，不能直接当作已经排除稀疏依据先生成的实证；同样
不能据这次扫描声称删除前历史或其他命名工件从未试过。审计
`monitoring/past_actual_native_field_orders_and_unignored_source_exposure_audit.json`保存范围与摘要。
这些是可验证的设计/历史边界，不是新方案效果证据。先完成冻结的两批与保持，避免
又仅靠改一个词、排序或更多卡片就称解决取证问题。

## 08:28完整B6与真实B7更新：确有错引，不再只怪漏检索

完整B6八新源/16真实回答已独立按作者原集合重算，same-M2空库83.82/63.19/44.12%，
完整示范＋程序76.47/57.14/33.82%（accuracy/原SPAN F1/joint）。标签8修18伤、联合
9修23伤；真成员5增20丢。丢失20中，15个E→E、4个C→NM、1个C→E，13个原本已
在普通候选。不是只有选择NM后证据被清空，亦不能靠候选召回一项解释。

369、193、548、378的nda-10原Gold均NM，空库均正确；加完整416示范后均变成E[12]。
当前12分别是定义标题、WHEREAS、客户关系前言、“as is”免责声明，公共理由却说
协议条款保密。过去416的相同命题原标注恰为E[12]，原句是协议存在和条款视为保密。
这比单纯集合重号更具体：选中的当前文本和给出的公共理由不符，且旧答案模式相同。
但尚未受控改变过去引用身份，不能据此把“坐标复制”写成唯一因果。未发现过去公司
名称串入的标记；18个分类损害中16个有同题过去示范，13个新错关系等于该示范。
完整逐题/原文/候选可见性：
`monitoring/B6_complete8_past_answer_identity_alignment_and_true_member_loss_root_audit.json`。

B7新教师1374已真实返回并用于后续作答。40历史均完整归档，实际包为B6全8＋完整416，
9源/Gold/真实own；无B7源、其他臂答案或私有推理。4UPDATE把全部示范换为完整378
及17原答案，NM11/E4/C2，master2413/scoped2693。24后续输入、保持时同源例排除、
610绑定及615归档成员独立核验；仍不能把工程通过说成有效。程序重写又出现
“securities proxy solicitation ... do not qualify”，而原334没入这9源回放包；这是
具体旧边界遗忘风险，不等于proxy单独支持人员招揽，也不在运行时手工改该条例。

下一受控区分须保持当前源、原17命题、当前原SPAN、同M2、同4字段生成契约和实际
发布程序不变，明确消融完整历史示范与其可混用数值引用。若改变表示，只能在新Run
记录，先冻结和备份，不覆盖本轮负面原始工件；即使解除错引也须继续不同合同学习、
保持及成熟对照，不能把修正坐标或高原案重答当作论文方法目标已经达到。

## 08:46终态与正在执行的机制干预

contextual Run03已完整40答结束；B7空库87.50/67.10/52.94%，完整示范＋程序
78.68/59.36/45.59%，标签4修16伤、真4增23丢。两新批合计85.66/65.15/48.53%
对77.57/58.25/39.71%，不能以B7裸分高于B6掩盖同批配对损害。B6后续保持
81.62/56.54/47.79%，比原技能阶段的联合正确率高，但TP82→80；与同案空库相比
NN exact同31，联合多出的5题全是NM。所有40真实wire、原集合及实际成本独立核验，
不是训练和测试混合出来的好分。

预注册historical_identity_ablation Run01已于08:42后台真实启动。两实际学习状态
B6/B7、同16预选合同：一臂用可逆字母证据键替换过去整数引用，保留完整过去源和
原标注；另一臂仅移除过去示范，保留完整程序/作用域。当前源、17题、原整数SPAN、
M2、4字段生成契约和所有生成参数不变，32新native/0新教师。首592两臂实际输入
和完整合法回答通过，未作零散质量评分。它测试“类型化历史引用表示”和“完整示范
是否干扰”两种干预，不声称已经证明心理上的唯一复制原因或已经有效。

父40原始输出、真实教师、两版库和新32输入/源码/Git在首答前保全并独立复验691成员；
运行684绑定另加绑定清单自身为归档685项目项，已在prefix2审计更正此前数目措辞。
当前边界/类型化表示尚未升为正式主方法，仍须后续真实学习、不同合同/保持/公平对照。

另核查9月4日的[Skill-Evo4GUI作者仓库](https://github.com/LongtaoHu/Skill-Evo4GUI)，
固定commit d13b1b5097f951c74e540270785d325eb108c45d：公开主要是执行/提案提示、
schemas和示例技能，并非完整可直接跑的OSWorld复现。可参考的是当前状态匹配前置
条件、区分技能问题与执行问题、跨轨迹检查持续误触发；没有把其额外角色、硬数量
门槛、重试/熔断或新环境带进来，也未据此声称在法律任务有效。原文件及哈希见
artifacts/research/experience_faithfulness_20261017/skill_evo4gui_recent_primary_prompts_provenance.json。
