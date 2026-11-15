# C的负作用、第二项证据与实际修复

2026-11-15。**现有结果不支持两项贡献成立，效果问题尚未解决。** Goal继续active、未完成；本轮新增模型调用0，未启动新完整训练或TEST。

## 基线与消融

同一固定40母来源/88视图的母来源原生评分均值，包含OpenExempt F1等，不能统一称准确率。

|系统|此前有效DEV|最新有效DEV|
|---|---:|---:|
|空库 NoSkill|48.134%|48.134%（同一历史快照）|
|共同底座 FreeEvolution|48.134%|48.134%（同一历史快照）|
|同信息普通教师源获取＋普通教师观察|45.634%|45.634%|
|ours：C＋学得观察＋残余补读|47.509%|46.884%|
|去掉C，保留相同观察与补读|48.134%|48.134%|
|C＋固定通用观察|45.009%|44.384%|
|C＋普通教师观察|47.509%|46.884%|
|C＋学得观察＋普通补读|47.509%|46.884%|

旧Full的真实历史结果59.330%继续公开。其获取轨迹不同，不是当前C/第二项严格消融，也不能隐藏它、只和较弱控制比较。[三份历史基线原件](baseline_evidence/)、[此前有效七系统](raw/legal_skill_evolution_mixed_DEV_public_execution_20261115/scored_results.json.gz)、[最新有效七系统](raw/legal_skill_evolution_mixed_component_DEV_profile_fix_20261115/scored_results.json.gz)。

## C：已定位什么，修复是否解决负作用

最新ContractNLI为18/32，NoC为20/32：C修正4个视图，同时误改6个，净损失2个，对全部40母来源均值贡献为−1.25个百分点。覆盖增加和原TRAIN的93/96不能代替泛化收益。当前待解决的是源表示与题目消费者的语义衔接、新源读取可靠性，固定八批已经完成。

三个TRAIN残余的根子集及全37规则包络反证直接复用：现有表示不足以在保持源检查下修正。不能把受控公司员工补成本公司员工、请求补成终止、或把返还/销毁OR强化成单项义务来拟合标签。这不证明标注错误或法律推理普遍不可行。[原反证](raw/legal_skill_evolution_source_residual_diagnosis_20261115/result.json)、[全规则包络](raw/legal_skill_evolution_source_residual_diagnosis_20261115/all_rules_envelope.json)。

本轮发现公共许可计数修复以原教师编译候选为父版本，同时恢复了G选解移除的两条规则。对原24个TRAIN来源的相同付费读取执行三处实际变化隔离：

|相对B8已选G的变化|原生正确/96|未执行视图|
|---|---:|---:|
|无变化|89|4|
|仅恢复原子返还|91|2|
|仅恢复受控公司员工|89|4|
|仅加入带许可计数守卫的缺失判断|91|2|
|原子返还＋带守卫缺失判断|93|0|
|全部三项（此前公共修复候选）|93|0|

全部8种实际组合通过现有源硬检查，未新增来源或模型调用。这是归因三个已发生修改，不是扫描新参数。按原定native loss→相对已接受B8的编辑数→复杂度，选定候选101（3、2、47），此前111为（3、3、49）。选择只用TRAIN，不声称整个G语言的全局最优，不把部分源检查称完整语义证明。[8组执行](raw/legal_skill_evolution_source_selection_lineage_20261115/result.json)、[选择及父版本](raw/legal_skill_evolution_source_selection_lineage_20261115/selection.json)、[锁定候选](raw/legal_skill_evolution_source_selection_lineage_20261115/training_selected_candidate.json.gz)。

先锁定TRAIN候选，再对已有DEV付费观察作一次确定性影响追踪；没有重新生成、继续选解或修改候选。**所有消费者答案和七系统分数不变。** 因此已补齐修复后的选择环节，但多余规则不是当前DEV负增益主因。旧冻结库和原DEV保持原样，不把这个候选报成涨分或C成立。[预先锁定](raw/legal_skill_evolution_selected_source_effect_replay_20261115/pre_replay_lock.json)、[0调用影响追踪](raw/legal_skill_evolution_selected_source_effect_replay_20261115/result.json)。

## 旧U和当前第二项

旧U的修订影响范围学习没有独立收益证据，已降级保留。当前第二项研究从错误学习观察表示/转换程序和残余补读，不能把替代方向的产出算作旧U成功。

最新SARA方法主路径正确1/8，普通教师2/8，通用表示5/8。方法和普通教师含fallback均6/8，但分别7/8和6/8回退。C＋普通教师观察与ours同分；同契约残余/普通补读的5个实际机会各额外解决0题。**独立学习收益和残余读取收益均未证实。**

真实family修复在两例原TRAIN使方法主路径1/2→2/2；普通教师也学会同一亲属修复，来源令牌编译消融增量0。它证明局部故障可修，不证明新机制更强。[真实生成、复用及否定消融](source_guard_repair/README.md)。

本轮另确认农业工资和服务期间被读成学校、入学、到课及就业终止。原schema和转换器接受教育记录，但**同schema也允许complete空数组**，并未迫使模型编造。属于模型语义误读，另有部分源反馈漏报。现补入原TRAIN两条明确源检查，两臂共用；漏报0变为记录2条违规，不删除模型事实、不替换答案。原整案仍未执行，不计新增成功。空数组只是schema表达能力探针，不是修复后的模型预测。[原记录与前后检查](raw/legal_skill_evolution_observation_semantic_audit_20261115/result.json)、[原始整案](raw/legal_skill_evolution_observation_semantic_audit_20261115/actual_case.json.gz)。

## 当前判定与后续

本轮补齐G更新选择/父版本记录和一条真实误读的源反馈；8组TRAIN执行、既有DEV缓存一次影响追踪及17项相关回归通过，未获得新DEV增益。仍需解决C的语义衔接与泛化负作用、第二项合法完整输入的可靠性，以及相对普通教师和普通补读的独立作用。三库继承共同底座也不能算新机制已学会五库。

继续现有Goal，在原TRAIN真实错误上改进观察学习与更新选择，保留同信息普通教师控制；只有明确机制/代码变化、离线证据和具体后案复用问题齐备时才进行必要真实验证。不重复同例无变化请求、相同G实验或固定DEV追分，不把公共修复另起名字当贡献。

本轮executor0、teacher0，累计executor10853、teacher303，reserved0；前后11156条请求逐字段hash一致。没有新增模型token或请求费用，离线计算未单独分摊现金成本。thinking OFF，原始结果、冻结版本和账本保持。[本轮账本校验](raw/legal_skill_evolution_source_selection_lineage_20261115/result.json)、[逐次请求](physical_requests.json)、[现有费用](cost_snapshot.json)。
