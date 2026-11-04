# 当前论文质量、指标与论证审查

审查日期：2026-11-04，Asia/Shanghai。对象为当前 v15 对应的中英文主稿、两幅图、13 张表、参考文献及其原始实验记录。

## 1. 结论

当前论文的主表成绩有可追溯的原始响应支持，本轮未发现主表 F1 算错、失败回答被漏算、中英文实验数字实质冲突，或原始冻结配置被事后修改的证据。**但存在一项需要优先修订的附加指标问题：`Exact target` 是表示敏感的解码对象相等，不是“整案法律答案全对率”，而且与 EV 的空资产输出约定不完全一致。** 官方原生 EC 对空目标资产的评分约定也应明确解释。

写作方面，英语没有发现成片的基本语法错误；主要问题是部分术语含混、贡献表达偏泛、否定式边界说明重复。应把论证集中在“持续修订相较初始技能库的分类收益”和“教师看见实际执行错误的增量价值”，而不是再换任务或追求所有端点都第一。

本轮是审查，不是新实验，也没有覆盖主稿。按师兄 paper-writing skill，下面先给出原句、建议改法与依据，待确认后再同步改中英文稿及导出文件。

## 2. 本轮实际核验了什么

完整只读命令、输出、文件 SHA256 与定点文献核对记录见：

[数值与来源复核证据](../../artifacts/research/openexempt_skillcommit_20261102/manuscript_quality_review_readonly_reproduction_20261104.json)。

| 核验对象 | 本轮结果 |
|---|---|
| 11 条件、2,816 份冻结测试回答 | 用未修改的评分代码逐条重算，完整 score 字典不一致数为 0；11 组汇总不一致数为 0 |
| 原始服务器响应 → 提交 → 解码 → 评分记录 | 2,816 条均吻合；2,816 个不同原始响应路径和响应 ID；未发现额外数值求解器执行回执 |
| 评分前预测存档 | 去掉 score 后，与评分记录逐项一致，差异为 0；保全链仍需结合原有冻结、时间及清单证据理解 |
| 格式失败 | 37 条全部是 length 终止，全部保留为零分；没有修复后冒充原始首答 |
| 原 18 个端点的配对统计 | 20,000 次、原种子和原比较族复算一致；15 个调整区间下界为正 |
| SkillCommit 两端点补充统计 | 20,000 次、原补充种子和独立两端点比较族复算一致 |
| 8 批训练曲线 | 重算三条曲线对应的 768 个记录视图，包含既有响应复用；原分数、图源数据、112 来源汇总均一致。这不是 768 次独立生成 |
| 中英文 13 张表 | 数字逐表对照，无实质冲突；唯一程序提示是 0.01 F1 与 1 个百分点在中英文里叙述顺序相反，含义相同 |
| 冻结推理成本 | 从原始响应 usage 汇总，与表 D4 的 11 条件 token、终止和失败计数一致 |
| 主方法教师成本 | 从 16 份响应 invocation usage 重加：输入 1,778,335，输出 66,439；缓存输入和推理输出按子集计，未重复相加 |
| 实际技能演化 | 比较全部 8 个发布库：始终 7 条记录，B1 后 16 次已有任务投影修订、1 次 EV 投影新增；与表 D1 一致 |
| 训练/测试划分 | 各 128 个来源，来源键交集为 0；这是固定生成器内的来源隔离，不是跨法域迁移 |
| 冻结文件绑定 | 主方法 379 项及 SkillCommit 648 项绑定逐项 SHA256 一致；两份清单存在重叠，不将其说成 1,027 个不同文件 |

这证明的是：**保存的原始响应、解码、评分、图表和正文之间一致，可以复算。** 它不是独立重新学习一遍，也不能仅凭本地日志对外部模型服务来源作密码学认证。本轮未调用答题模型、教师或付费 API，未启动训练。

## 3. 需要优先处理的问题

### P1：Exact-target 的解释与任务输出约定不完全对齐

位置：英文和中文主稿第 207、274、276 行；实现位于 `legal_skill_guard/openexempt.py:241`。

实现是 `answer == target`，即 Python 解码对象比较：字典键顺序不影响结果，但列表顺序、数值相等以及是否存在空数组资产条目都会影响结果。它不沿用原生评分器的金额容差，也不等于法律声明集合完全正确。

| 主方法诊断，均为 128 案 | EC | EV |
|---|---:|---:|
| 已发表在当前工作稿中的严格对象匹配 | 74 / 128 = 57.81% | 53 / 128 = 41.41% |
| 只忽略列表顺序，其他内容保持完全相等 | 93 / 128 = 72.66% | 60 / 128 = 46.88% |
| 完整输出 F1 恰为 1 的案例数 | 93 / 128 = 72.66% | 63 / 128 = 49.22% |

第一处影响是顺序：19 个 EC 案和 7 个 EV 案只是列表顺序不同，就未获严格匹配。以上后两行仅是本轮诊断，**不是替换后的论文成绩，也不是新增预定主端点**。

第二处影响是输出契约：`decode_asset_references` 要求提交全部资产 ID，无适用依据时填 `[]`；但五个 EV 标准答案省略了某些零声明资产，分别是 3000011、3000042、3000096、3000111、3000125。一个完全遵守接口的回答在这五案不可能与原目标对象严格相等，该 EV 诊断的结构性匹配上限因而是 123/128 = 96.09%。其中三案的主方法完整输出 F1 已为 1，却仍因空条目表示差异不获严格匹配。

这不是主表 F1 错误，但现有“高声明覆盖 vs 整份答案匹配”的表述容易被理解成法律正确率，应该修订。

建议默认处理：保留全部旧值、原始对象与分析文件，将列名改为 **Strict decoded-object match / 严格解码对象匹配**，在附录一次说明顺序和空条目敏感性；正文不把它解释为整案法律正确率。不要偷偷把 57.81/41.41 换成更高的数字。

如果以后确实需要一个整案声明正确率，可统一对所有条件明确报告“完整输出 F1=1 的来源比例”，保留原诊断并说明这是补充分析；无需调用模型。但本轮没有擅自增加或替换端点。

### P2：官方原生 EC 的空目标约定需要解释，而不是改评分器

位置：第 124、266 行及表 B3。

本轮将 256 个参考答案分别与自身评分，得到：

- 原生 EC F1：98.502604%；原生 EV F1：100%。
- 完整输出 EC/EV F1：均为 100%。
- 五个带零适用依据资产的 EC 案导致原生分数下降，与上述五个来源一致。

原因是固定版本的原生 EC 评分器对空目标资产给零，再做资产平均；即使模型正确输出空集合也一样。因此，主方法原生 EC 95.46% 不能读成 95.46% 的案件全对，完整输出 96.67% 高于原生 F1 也不是算错。

建议在附录 B.2 增加一段明确的零目标约定及这次参考自评分诊断，保留官方原生 F1 为主端点。**不调整历史分数，不用 98.50% 对主表重新归一化，不把自评分诊断伪装成模型结果。**

### P2：贡献应更精确，不能将整个学习策略的收益归因于单一规则

当前稿件已经保留了重要事实：主方法 EV 为 87.90%，严格策略控制为 89.01%；二者配对差 -1.11 个百分点，调整区间 [-6.20, 3.65]。这是正常、可解释的结果，不构成数值矛盾，也没有必要把高分控制删掉。

真正有证据的论证链是：

| 主张 | 证据与判定 |
|---|---|
| 终库让固定 8B 在两个任务上显著优于强空库 | EC +30.98、EV +32.02 个百分点，调整区间均为正；VERIFIED |
| 后续进化超出首批技能获取 | 最终相对自身 B1 的 EC +11.95 [7.33, 16.60]；另有 112 个后续来源的同案首答对照；VERIFIED |
| EV 持续学习也有相同强度的统计证据 | EV +3.65 [-2.82, 10.28]，不能建立同等级的调整后显著结论；DESCRIPTIVE ONLY |
| 教师看到实际执行证据有用 | 相对隐藏执行证据控制，EC +8.48、EV +7.53，调整区间均为正；SUPPORTED FOR THE RETAINED PROTOCOL |
| 当前准入/选择策略有分类收益 | 相对严格策略 EC +15.17，EV 没有优势；SUPPORTED AS A POLICY BUNDLE |
| 放宽某一条计数否决本身造成上述收益 | 固定主方法既有输出时，九次提交也都满足严格门槛；不能单独如此归因；UNSUPPORTED |
| 任务保护、执行示例、分量提交各自均被独立消融证明 | 当前两项控制没有逐个隔离这些设计；不能写成三个分别验证的因果贡献；NOT ESTABLISHED |

ExpeL、ACE 已使用经验和错误反馈；GSE、SkillCommit 已使用重放验证。论文新增点应落在本研究的具体组合与证据：任务保护的法律程序修订、面向完整输出的库级效用检验，以及与自身首批库分离的持续学习评价。不要将“重放”或“法律技能进化”本身写成首创。[GSE 原文](https://arxiv.org/html/2608.06153v1)和 [SkillCommit 原文](https://arxiv.org/html/2608.15165v2)均已有相应机制。

这主要是进一步聚焦既有论证，不是发现稿件已经宣称了所有这些过强结论，更不是要求现在再换方法。

### P2：外部适配的分数有来源支持，但结论限于同接口比较

静态库和 Trace2Skill–Text 分别为 60.40/55.34、55.08/53.31%，低于强空库 64.48/55.88%。这些结果从原始响应可以复算，不能因为方法名字强就认定低分是假的，也不能据此断言原论文方法本身无效。

本轮确认所有 2,816 个请求使用相同的 Qwen3-8B、seed 45、temperature 0.6、top-p 0.95、top-k 20、8,192 最大输出条件。原生 ACE 有自己的公开推理/引用封装，另有共同接口行；原论文环境、库构建预算与本地适配并不完全相同。

SkillCommit 的 21 条模式加 23 条残余补丁是存储量；实际测试每题四条完整模式、EV 固定选中同四条是部署事实，不能把 44 条都说成被模型有效使用。原论文使用不同的嵌入服务；本地 BGE 版本是明确的适配。[SkillCommit 实现细节](https://arxiv.org/html/2608.15165v2)也区分了构建与推理预算。

当前表中已经写出 adaptation、common interface，并单列构建条件与成本，方向正确。应保留这种命名，不把本表包装成“复现原论文官方分数”或“官方 Advanced SOTA”。无需为了让分数排序好看重跑或删改比较。

### P3：英文主要需要术语和论证压缩，而非大规模语法重写

以下并不都是语法硬错：

- `independent answers` 易被理解为统计独立，实际上 EC/EV 共享来源且配对分析，应改成 `separate answers`。
- `source`、`source case`、`source-isolated` 反复交替，宜首次定义来源案件，后文统一表述为 `source-disjoint cases` 或 `new cases`，不改变划分含义。
- `publication` 同时可能指论文发表和技能库提交。方法首次出现时明确为 `library commit`，后文统一，代码路径可以继续叫 publications。
- `reference solutions alone` 过度二分；控制还有控制器的间接重放反馈，应写成“在参考和既有控制反馈之外增加实际执行错误”。
- 讨论、附录、成本部分反复用 `not`、`rather than` 排除其他解释。一部分是必要定义，不能删除；其余可以合并到相应方法/统计位置，不要在每个结果后重复。

Anti-Defensive Writing 在这里用于把论证转成“问题—机制—证据—结论”，不是用于省略真实比较条件、隐藏 EV 对照结果或消除必要的数据来源说明。

### P3：两项可核实的书目信息修订

1. Qwen3 当前按团体作者 `Qwen Team` 记载，官方技术报告及仓库推荐 BibTeX 使用 An Yang 等具体作者。建议按[官方 Citation](https://github.com/QwenLM/Qwen3#citation)统一作者字段，联动更新中英导出的作者年份引用。这是书目规范化，不是发现了假论文。
2. JustifIT-QA 当前条目缺 DOI。官方 ACL 页面提供 `10.18653/2026.emnlp-main.593`，可补入。[官方书目记录](https://aclanthology.org/2026.emnlp-main.593/)

本轮对 11 项文献核对了主要元数据，并对稿件用到的机制描述作定点核查，未发现不存在的论文或明显张冠李戴。ExpeL 主页面有反爬限制，作者、题名、年份和页码改用出版社自己的 citation endpoint 核实；不将“访问被拒”说成文献失效。ACE、ReasoningBank 的预印本年份与后续接收年份可在选刊后统一格式，不能简单把两个年份判成矛盾。

## 4. 可直接采纳的中英文改句清单，尚未写入主稿

### R1：明确严格对象匹配定义，优先级最高

位置：第 274 行及表 B3 列名。

原句：`Exact-target matching compares the decoded full answer with the reference`。

建议英文：

> Strict decoded-object match requires equality of the decoded answer and the reference, including list order, numeric values and the presence of empty asset entries. Dictionary key order is immaterial. This representation-sensitive diagnostic is reported separately from claim-level F1.

建议中文：

> 严格解码对象匹配要求解码答案与参考对象相等，包括列表顺序、数值和空数组资产条目是否存在；字典键顺序不影响结果。该表示敏感诊断与声明级 F1 分开报告。

依据：对象相等实现、全矩阵顺序诊断及五案 EV 输出契约差异。表内原值不变；附录紧接说明五个 EV 参考省略零声明资产。

### R2：去掉把严格匹配读成法律全对率的暗示

位置：第 207 行。

原句：`These measures distinguish high claim coverage from an entirely matched answer.`

建议英文：

> Complete-output F1 measures the quality of the full claim set; strict object matching additionally depends on output representation, as specified in Appendix B.3.

建议中文：

> 完整输出 F1 衡量整份声明集合的质量；严格对象匹配还受输出表示方式影响，定义见附录 B.3。

依据：19 个 EC 顺序差异及 EV 空条目差异。保留 96.67/87.51 和 57.81/41.41，不混成一种指标。

### R3：解释原生评分器的空目标约定

位置：第 266 行后，新增一次定义即可。

建议英文：

> In the pinned native EC scorer, a target asset with no applicable citation contributes zero even when the predicted set is correctly empty. Consequently, the references score 98.50% against themselves on this EC packet, whereas their complete-output F1 is 100%. We retain the native scorer unchanged.

建议中文：

> 固定版本的原生 EC 评分器对无适用依据的目标资产记零，即使预测正确为空集合也如此。因此，本批 EC 参考答案与自身比较的原生 F1 为 98.50%，完整输出 F1 为 100%；本研究保留原生评分器不变。

依据：256 个参考自评分的离线诊断。它是评分约定解释，不是模型能力结果，也不是新的归一化指标。

### R4：摘要开头直接提出要验证的学习问题

位置：第 7 行前两句。

原句：`Reusable instructions offer a learning interface for small language models whose weights remain fixed, but an initially useful memory does not establish that further experience improves it. We study this distinction in statutory exemption classification and valuation, where an answer must preserve independently applicable alternatives and assign their protected amounts.`

建议英文：

> We study whether reusable legal procedures continue to improve a frozen language model after initial skill acquisition. The tasks are statutory exemption classification and valuation, which require identifying all independently applicable provisions and assigning their protected amounts.

建议中文：

> 我们研究初次获取技能后，持续修订可复用法律程序能否进一步改善冻结语言模型。研究任务为法定豁免分类与估值，需要识别各项独立适用条款及其受保护金额。

依据：直接建立“初次获取之后是否仍有收益”的研究主线；不改变后面的结果或扩大 EV 结论。

### R5：分别作答不等于统计独立

位置：第 33 行。

原句：`The two tasks share source facts but produce independent answers.`

建议英文：`The two tasks share source facts but are answered separately.`

建议中文：`两个任务共享来源案件事实，但分别作答。`

依据：分析按来源保留 EC/EV 配对；这是术语澄清，不是说原 bootstrap 错了。

### R6：更准确地表达执行证据控制的收益

位置：第 201 行。

原句：`This supports grounding revisions in observed execution errors rather than reference solutions alone under the retained learning protocol.`

建议英文：

> This increment supports adding observed execution errors to the teacher's released-target evidence under the same replay-based admission protocol.

建议中文：

> 这一增量支持在同样采用重放准入的学习协议下，向教师提供已释放目标之外的实际执行错误。

依据：控制器仍会重放和准入，不能被缩写成毫无反馈的“纯答案条件”。保留两项显著收益，减少二分式表述。

### R7：把泛化的贡献句改成可定位的方法与证据

位置：第 23 行最后一句。

原句：`The contribution is an execution-grounded learning loop for legal procedures, supported by separate evidence for initial library utility, subsequent evolution and the value of teacher-visible execution errors.`

建议英文：

> The method couples task-protected procedure revision with all-seen utility checks on native and complete-output F1. The fixed first-batch comparison measures continued revision separately from initial library acquisition.

建议中文：

> 方法将受任务保护的程序修订与基于原生、完整输出 F1 的全已见来源效用检验结合；固定首批库的比较则将持续修订收益与初次获取技能区分。

依据：具体描述既有机制及关键证据，而不是重复“我们提出学习闭环”；不声称任务保护已被单独消融证明，也不将已有重放思想冒充首创。

### R8：讨论用正面机制陈述替代重复排除句

位置：第 211 行最后两句。

原句：`The teacher acts during learning; the frozen executor still selects provisions and amounts itself at test time. The learned state therefore consists of reusable instructions rather than a second answer-generating model or a privileged numerical solver.`

建议英文：

> The teacher revises the library during learning; at test time, the frozen executor directly generates provisions and amounts using the retained procedures.

建议中文：

> 教师在学习期间修订技能库；测试时，冻结执行器根据保留的程序直接生成适用条款与金额。

依据：同一事实在任务接口与方法末尾已说明；这里突出实际工作机制即可。方法中关于直接数值生成、标签可见性和工具边界的定义仍保留。

### R9：合并讨论中重复的解释边界

位置：第 217 行。

原段包含：`it does not show a uniform valuation advantage`、`with independent learning builds reported separately when available` 等已在结果和统计方法说明的事实。

建议英文：

> The evidence concerns new cases from the pinned generator with facts, statutes and allowable jurisdictions supplied. Matched controls quantify the contribution of execution evidence and the classification benefit of the joint admission/selection policy; paired intervals quantify case variation for the retained libraries.

建议中文：

> 证据来自固定生成器内已给事实、法条和可适用法域的新案件。匹配控制量化执行证据的增量贡献，以及准入与选择组合策略的分类收益；配对区间描述保留技能库上的案件变异。

依据：结果部分仍明确 EV 不占优、继续学习 EV 区间跨零；方法和附录仍明确单次构建与补充测试关系。合并重复不等于删除这些事实。这里的策略效用应结合前文分类结果理解，不写成所有端点均获益。

### R10：中文相关工作用词与 judge-based LLM 对齐

位置：中文第 29 行。

原句：`将法条检索与判别模型引导的回答修订结合`。

建议中文：`将法条检索与大语言模型评审反馈驱动的回答修订结合`。

英文现有 `judge-guided answer refinement` 可保留。依据：[JustifIT-QA 官方摘要](https://aclanthology.org/2026.emnlp-main.593/)描述的是 LLM critique/refinement，不是另训一个判别器。

## 5. 图、导出与论文完成度

两幅图本轮重新查看：方法图呈现首答保存、标签释放、任务修订、全已见来源重放与提交；学习图保留八批原始波动，没有平滑或标签后重答冒充首答。固定 B1 曲线的绘制从 B2 开始，与图注一致。

本轮还查看 EN 第 8、22 页和中文第 7 页。主表视觉上曾疑似数值靠近，进一步用 PDF 文字边界框核对，抽查 EC/EV 数字间实际有 40.3 pt 间距，没有数字拼接；不将视觉猜测列成错误。中文存在把拉丁单词或小数跨行拆开的可读性问题，可在最终导出时改善。这里不是声称重新目检全部 42 页；先前 13 个关键页的检查记录仍独立保留。

当前源文件 SHA256 与 v15 导出清单一致，没有在审查期间混用另一版主稿。当前稿可以进入有针对性的终稿修订，但投稿材料仍有作者、目标期刊、实际声明、最终数据/代码访问地址和项目许可证需要确认；这些与主表数值是否真实是两类问题。独立重复学习仍是已明确延后的证据补充，不能把来源 bootstrap 叫作学习随机性的重复实验。

## 6. 建议的下一步顺序

1. 先实施 R1–R3，修正附加严格匹配解释并补充官方空目标约定；不改任何已保存分数，不启动模型。
2. 同步实施 R4–R10，统一术语、压缩重复解释、把贡献落在已有证据上；同步规范两项书目信息。
3. 重新导出新版本中英文 Word/PDF，重点检查变动页、两张主结果表、引用与数字，不覆盖 v15。
4. 当前发现不要求重跑八批、外部方法或冻结测试，也不要求为了曲线好看重选随机种子。独立重复与迁移等后续实验如另行决定，单独计划，不混入此次文字修订。

师兄 skills 约束了本次“先审查、给具体改句、再经确认改主稿”的流程；Anti-Defensive Writing 使建议优先强化已支持的论证而不是增加免责段；nature-paper 用于限制指标与因果措辞的精度。以上建议均未写回主稿，原始实验、原分数和旧导出均保持不变。
