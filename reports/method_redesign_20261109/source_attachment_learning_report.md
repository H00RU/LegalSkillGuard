# 部分源反馈附着学习：真实强对照与固定来源结果

**完成了可运行学习算法、真实输入、参数更新和冻结强对照；当前候选没有成立为第一项贡献。** 两个学习器在三条TRAIN约束上均通过，修正检索和普通词法/树程序也通过。固定4个原TRAIN来源中，3个切片可执行，但候选的选择及源状态与冻结提案先验完全相同；另1个获取失败。停止为这个重排候选追加模型请求，不以训练拟合或IR恢复结项。

同一Goal active、未完成。目标/验收/授权唯一见[CURRENT_GOAL](../../docs/CURRENT_GOAL.md)，当前证据及下一工作唯一见[METHOD_REDESIGN_CURRENT](../../docs/METHOD_REDESIGN_CURRENT.md)。本报告是实验记录，不新增执行要求。

## 实际学得什么，更新如何运行

学习对象是源解释与限定/引用/例外绑定的共享参数。每个已有源声明有若干带引文的解释，程序用`P/O/F/BREACH/NOT`区分许可、义务、禁止、违约后果与否定。学习器枚举类型合法的联合解释，最大化所有满足部分源反馈及已有原生TRAIN监督的解释的总概率，采用一次固定的单位高斯正则；hard-EM只选一个兼容解释更新。没有参数/seed扫描。

跨来源特征包括算子组合、原文词项与各层算子的对应、限定片段角色、例外两端动作/参与人/信息绑定。曾发现根节点特征不能区分同为`NOT`根的不同谓词，已在读取预留来源前修复，并用实际响应上的表示能力回归验证。**这是普通条件log-linear模型，不主张CRF或其等价线性改写是新数学机制。** 作用只能由法律源获取/更新的实际对照证明。

作者从已有TRAIN15/20/111核实三条部分源结构约束：引用限定禁止、披露属于否定违约的条件、留档例外关联返还义务且共享参与人及基础信息。它们是新增/细化的作者监督，双方全部获得；不是模型自行发现的知识，也不是新增原生问题或标签。记录3母来源/3约束，人工时间未计时，不能报零成本。[逐条监督及支持跨度](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/author_checked_partial_source_feedback.json)。

实际参数状态已保存、冻结、重新加载执行；两个学习器均优化收敛。当前三个约束的兼容拟合为3/3，而不是三份完整源规则已经全部正确。原8题回归仍8/8，主要继承旧缓存，不计8次新核心学习。

[学习实现](../../legal_skill_guard/rr/source_attachment_learning.py) · [源森林编译](../../legal_skill_guard/rr/source_attachment_forests.py) · [真实生成/学习入口](../../experiments/rr_v2_source_attachment_learning.py) · [保存的参数](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/learned_attachment_parameters.json) · [冻结前控制结果](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/controls_and_training_replay.json)。

## 输入、旧知识和学习作用分开

本轮9个真实Qwen请求均thinking OFF、reasoning为空、正常stop，没有截断。第一次只返回1/4声明；改为逐声明必填schema后覆盖完整，但仍有引文改写和否定接口混淆。后续用单层表达式记录含义，保留每次原始失败及代码版本。

原15的响应写了`F(share(third_parties, Confidential Information))`。只有动作、接收域、对象都与同一响应/声明唯一一致时，编译器才把显式操作数绑定成`A`；外层`F`或`NOT(P)`不改写。case/空白适配也须找到唯一原文形式，不替换`will/shall`等实词。

限定片段的condition/reference/context归属和同一引文单元中的例外边被明确列为潜在解释，不是把模型原输出偷偷改判正确。所有控制看到同一候选、解释器和来源。原111的新模型遗漏P、发出`O(retain)`，**没有将O猜改为P**；已付费普通源程序原本就有正确O/P头，它们作为单独标明的旧知识候选复用。不能计为新模型或新方法取得了这些头。

信息解析器仅在同一支持单元有唯一带所有者的先行词、并有明确`such`引用时解析基础Confidential Information；保留“all copies”和“a copy”原文，不将物理副本集合等同。该解析器也是公共组件。原响应只有缺失对象/歧义引用时不填值。

原15、20、111的现有物理响应经过**完整模型payload相等**检查被复用，后续拟合/恢复不重发。9次包含所有前端失败和变更后的真实重试；复用不重复计数。7项必要回归通过，软件fixture不作为真实法律样本或方法效果。

一个解释口径也已排除：没有锁定strong/weak permission时，`F(A)`和`NOT(P(A))`可能只是常见deontic对偶，不能用其差异制造学习增益。15只约束不产生新正许可与引用附着。`NOT(BREACH(A))`与“没有义务/没有禁止”则是不同法律后果。

[所有冻结输入与实际源码版本](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/seal.json) · [原15表达式响应](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v3_20261110/p15_forest.json) · [原20实际响应及恢复](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/p20_forest.json) · [111旧头/新字段的独立归因](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/p111_forest.json) · [必要回归](../../tests/test_rr_source_attachment_learning.py)。

## 冻结强对照与源复用

原114/116/117/118在生成前固定，未据结果改权重或选择器。切片规则也提前固定：优先已有return/retain配对，否则取原顺序两声明。这4个来源的旧源程序均未产出可选配对，实际8条均为share；**不等于原合同不存在返还/留档条款**。没有新增原生问题、预测或标签；8声明不是8个独立母来源。

| 路径 | 可见TRAIN部分约束 | 固定源上的主要观察 |
|---|---:|---|
| 候选边际学习 | 3/3 | 3个可执行切片与冻结先验的选择/源状态完全相同 |
| 同信息hard-EM | 3/3 | 主要算子与候选相同，部分限定/引用角色不同 |
| 冻结模型提案先验 | 0/3 | 是比较更新作用的实际原始先验 |
| 同材料修正检索 | 3/3 | 114选择F，117仍为NOT(O)，未建立完整接收范围/条件语义 |
| 普通词法/树程序 | 3/3 | 117选回原文明确的F主算子；仍不能称整源通过 |

这轮没有再购买独立自由程序更新，因为廉价强控制及不变输出已足以否定晋升本候选；旧独立普通获取/修补结果继续保留。若未来有正向方法主张，仍须完成相应独立获取/更新比较，不能以此省略强基线。

主路径尝试4/4，形成可执行共同森林并执行选择3/4；显式fallback未启动，0/4。116保留为未解决获取错误。TRAIN已选四个头中，111的P头来自旧缓存（1/4）；新源候选所选六个头均来自原Qwen提案，但学后选择未变。普通树控制在114/117各复用了两个旧头，单独记录，不能叫新模型学得的规范。[旧头与fallback逐项归因](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/seed_and_fallback_attribution.json)。

| 原TRAIN母来源 | 实际情况及未解决项 |
|---|---|
| 114 | 2/3旧声明被选。读者把不同接收范围都锚到一般禁止句，另把员工许可留在限定片段中。候选仍为两条`NOT(O(A))`，没有恢复接收人对应的许可/禁止及同意条件。 |
| 116 | 2/3旧声明被选。第二声明把原文`will disclose`引成`shall disclose`，全部读法因此拒收；这是模型实词改写，不能作为格式适配。未用旧结果补成新方法成功。 |
| 117 | 2/4旧声明被选。原文两条`shall not ... disclose`，候选/先验仍选`NOT(O(A))`；普通树程序选`F(A)`，主算子更忠实。4.3及列举例外仍是额外限定缺口。 |
| 118 | 2/4旧声明被选。五路径相同；定义来源声明与实际禁止共享了禁止跨度，且遗漏明确的事先书面同意条件。没有新增有效规范或学习增益。 |

`NOT(O(A))`表示没有某行为义务，不能替代原文对该行为的明确禁止。以上是源切片语义核查，**不是原生0/4分数或新的全库准确率**。3/4森林可执行也不是3/4语义成功。跨行为绑定在TRAIN发生，预留切片中没有实际新配对，不能声称已验证其迁移；这不是给Goal追加全分支实测门槛。

[预定母来源/文档哈希](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/source_only_reuse_plan.json) · [复用前冻结](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/reuse_freeze.json) · [全部预测、原文与来源级状态](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/fixed_source_reuse_predictions.json) · [完整审计与源义核查](source_attachment_learning_results.json)。

## 问题归类与研究决定

已解决的工程问题包括声明覆盖schema、双重编码含义、显式动作操作数绑定、词项与嵌套算子关联特征、保存/恢复。它们不算两项方法贡献。116的实词改写及114/118的支持跨度/条件缺失属于模型获取错误。117在正确F候选可选时仍选NOT(O)，是本次学习/泛化失败。当前森林也只能解释旧程序已经提出的声明，不能发现旧程序漏掉的规则。

最近邻核查支持采用成熟工具，但不支持仅靠命名晋升：[FUBL](https://aclanthology.org/D11-1140.pdf)分离词项与组合模板；[潜在结构对齐](https://aclanthology.org/D19-1391.pdf)处理弱监督伪程序；[法律否定范围工作](https://arxiv.org/html/2309.08695v1)标注scope，但词处于否定范围不等于该行为被禁止。当前候选的问题不是这些算法“不够新”，而是没有取得强同信息对照下的独立作用。

**放弃已有候选的附着重排作为第一贡献，不继续扩大它的实例或优化器小试。** 真正未解决的是从原文取得正确节点、支配关系和条件。下一步只保留“词项与组合模板分开学习”的源获取路线做离线实现/反证，必须能改变实际候选覆盖并对照普通源解析/正确缓存；目前没有新的可晋升方法或继续追加真实实验的科学依据。后续取得新依据时仍在既有资源授权内自主推进，不新增逐轮索权。现有代码、负结果、账本和五库均保留，原Goal没有收缩或完成。不得据本报告启动主训练、TEST或论文。

## 费用与保存

新增**9E/0T**，全部正常结束，输入31032、输出4584、合计35616 tokens，实测生成129.927秒；9次均OFF且reasoning为空，无8192上限截断。后续源码绑定、候选扩展、参数拟合、保存/恢复及对账均0模型请求。客户端重试0；真实请求ID/原始响应全部保存。

本地执行器增量API现金0，GPU分摊、人工结构约束标注时间、项目累计现金未知，不将这些写成免费。原初始程序的教师费用及此前所有失败仍在历史成本中；本轮复用它不倒扣历史费用。教师未新增，原配置未改。

账本**1408E/74T、pending0，1482calls/236meta/145oracle**。本轮1473/231/145→1482/236/145，旧行逐项保留，0新原生标签视图。4个获批DEV继续封存，原128来源/TEST不改。原0/89全源执行器IR分母不变；这些源切片、旧头恢复与参数学习不并入其分子。

冷恢复的选择、源图与解释完全一致；浮点分数只有约3e-16的加法顺序差异，分数用1e-12容差核验，实际选择和语义结构仍严格比较。不是放宽正确性检查。

[逐物理请求差量](../../artifacts/rr_method_redesign_20261109/source_attachment_learning_v6_20261110/request_ledger_delta.json) · [可执行审计](audit_source_attachment_learning.py) · [冻结控制及解码](evaluate_source_attachment_learning.py) · [全部费用/回归/保存证据](source_attachment_learning_results.json)。
