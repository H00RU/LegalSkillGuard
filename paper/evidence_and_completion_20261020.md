# 当前论文证据与完成条件

更新：2026-10-24 12:30 CST。本页列当前可用证据与待完成内容，并保留累计阶段记录。
此前1130行开发与历史轨迹清单逐字保存在
[历史证据快照](revisions/evidence_before_ACEv4_20261022_2212.md)，不是当前结果表。
执行入口与句柄见[CURRENT_GOAL](../docs/CURRENT_GOAL.md)。

## 最新完整结果：Text45已结束，whole-bank消融已运行

Text45于24日12:03完成全部128案/256任务，末库EC/EV F1为52.74%/49.73%，
低于自身源空库60.17%/62.92%；原主终态同阶段为86.03%/89.30%，差33.29/39.56pp。
这是单seed的完整TRAIN拟合，不是在线曲线、正式TEST或作者原生方法SOTA结论。
原八批首答82.03%/79.16%不改，不混入这次同阶段比较。

全部256真实HTTP的system/公开案件/schema/模型/seed/预算、原始解码和原评分均核同，
512实际生成ID唯一，16条长度失败（EC4/EV12）原零分保留。格式有效任务在原128
分母上仍贡献−5.51/−8.61pp，故退化不只来自截断；该分解不删除输出、不识别单一
内容/执行因果根因。完整终态两盘各2505成员逐文件核对，原Text进程是正常结束。

Text库一文件3182tokens；512次8B用4,061,370输入/1,463,066输出，321教师/321尝试
用6,429,967输入/503,252输出，缓存/推理已含。墙时15.07h不是GPU忙时。
[完整拟合、实际请求、计分和成本证据](../artifacts/research/openexempt_legal_scope_20261020/Text45_complete128_256_actual_shared_actor_final_TRAIN_fit_vs_mainterminal_cost_dual_preservation_NOT_TEST_20261024.json)
支撑v0.14新增表3，不改表1/2、原始数据或任何训练代码。

原队列已实际启动空库whole-bank45消融，仍是同单实例8B。其结果、first-commit、
六次独立构建、正式16臂TEST和统计均未完成。以下累计账本中的早期等待/部分状态
是当时记录，当前完成状态以上述里程碑及原始制品为准，不据旧记录重跑已完成任务。

## 科学主线

研究冻结8B如何通过连续编辑可复用的法律程序性技能改善后续来源的规则适用。
原生EC评资产适用法条，EV还评法条对应金额。不是三分类、文书匹配、客户模拟、
参数微调或无标签TFGRPO。主文突出机制、训练收益、完整对比；调试细节不占据主线。
必要的监督、信息边界、成本、失败及影响结论的局限仍如实披露。

已完成八批有足够证据进入完整对照与论文成文。对照期间未重训，没有新增主方法
成绩不代表原有收益失效；当前保留该方法完成证据链，隔离教师交付修复不自动启用。
也不把一次有效开发轨迹预定为最终胜出：若成熟TRAIN对照或末库收益实质不足，
才依据TRAIN决定新版本与匹配重训。正式TEST不用来反复选择方法/库。
不能把原先已见开发来源改名为未见测试；不删不利对照或美化原始分数。

## 当前证据账本

| 主张 | 状态 | 原始支持或缺口 |
|---|---|---|
| 主Run03完整128来源、8批、256任务、8次唯一发布 | VERIFIED | completion自然完成，无failure；实际全部首答与发布齐全 |
| 所有本批回答先于本批标签和教师反馈 | VERIFIED | execute顺序、原始input/HTTP/answer、评分与教师记录；回放不替换首答 |
| 主执行器/评分没有随ACE修改而变化 | VERIFIED | 原6896246四个主actor/scorer仍匹配371绑定；不是整份旧源码当前未变 |
| 完整主训练实际消耗可核 | VERIFIED | 1158native生成/生成端点HTTP全stop，7655443输入/3232344输出；15教师、3232522输入/51361输出，含拒收工作，不是全部HTTP查询数 |
| 额外B1评测是主训练后期耗时的主要来源 | CONTRADICTED | 全程实际首答/学习引用1077、仅B1评测81，原1158不减；主B6的249中169为候选重放。224个逻辑B1评测记录不能当224次额外生成，也不把1077当反事实训练时长 |
| 学得库在后续TRAIN比同案强空库更好 | VERIFIED | 完整八批表；B8 EC83.90/EV85.21%，同案空库59.12/59.96%；不是独立TEST |
| 持续进化超过首批学得库 | VERIFIED | 全112个B2–B8来源EC+0.85565/EV+9.39396pp；B2按设计差0 |
| 真正额外更新后的后续来源增益 | VERIFIED | 全96个B3–B8来源EC+0.99826/EV+10.95961pp，未删不利批次 |
| 两任务都已经表现出同等强的持续进化 | UNSUPPORTED | EV持续收益较大；EC平均不到1pp，不能说同等强或统计显著 |
| EC弱收益只是新技能投递丢失 | CONTRADICTED | 96案80案指导/原HTTP与B1相同；16案改变均真实送达，10好3坏3平 |
| 所有EC准入拒收都只是门槛过严 | CONTRADICTED | 11个实际改变分量2接收、5有原F1损害、4有完整输出/负资产损害；未来放宽效果未知 |
| 被拒EC更新确有实际条款主张损失 | VERIFIED | 全11分量内容/全改变TRAIN主张、294次前后投递/228原调用核同；B6相关56来源中至少42个原F1降，主要漏报原正确一般财产条款 |
| 泛化改写或大教师输入已被证实是因果根因 | UNSUPPORTED | 观察到具体例子改写与损害同现；15请求输入123777–246267tokens，尚未做独立干预验证 |
| 教师确实接收了冗余法律观察 | VERIFIED | 896任务视图的empty/initial答案、评分、错误等相同；调用别名元数据可异，不把全部对象字节冒充完全相同 |
| 全部已经选定的有界历史反例都真实进入本次教师 | CONTRADICTED | 重建15输入/8批真实父状态，232应交条目实际211；21项被历史来源过滤删掉。31原HTTP/解码/原评分独立核同，18项原F1下降，14不同任务，不是232个案件 |
| 缺少的是当前批全部正确标签 | CONTRADICTED | 当前32任务仍全给；丢失的是部分有界历史反例，本次无状态教师没有这些事实/目标/前后回答。不能以历史上给过代替本次投递 |
| 主教师被CLI自动压缩已是已证根因 | UNSUPPORTED | 15独立新会话各一成功轮、无压缩/截断事件，实际123777–246267输入低于配置800000触发线；配置本身不证明远端最大容量 |
| 主教师获得所有学生完整推理 | CONTRADICTED | 896父观察/385不同原始调用都按显式1024字符尾段截取，原文/hash已核；不是自动压缩，也未证明影响大小 |
| 教师交付修复已独立实现且未热改当前实验 | VERIFIED | 隔离71906f6，全部232条历史输入回放可达、原标签/父回答/控制无损、未改推理/准入/更新AST；旧profile在后端访问前被拒绝。没有新训练或新指标 |
| 回放修复说明新方法已赢或可省相同比例计算 | UNSUPPORTED | 历史15包字符总量减6.58%、本地token估计减6.24%，个别包为补全反例更大；不是远端成本、新案收益或最终方法。采用须新Run重训及匹配验证 |
| 封存来源仅按不同案件ID冒充独立来源 | CONTRADICTED | 仅元数据核13个TRAIN packet共308个不同规范公开事实key，与封存128无交集；Case序列化无ID、key删除生成标签。recipe同、seed独立，未读TEST语义，不证明语义近重复全无 |
| 末库残余错误仍无可核具体模式 | CONTRADICTED | 全128来源256任务完整清单逐项匹配原完整输出TP/FP/FN；EC173漏报/19误报，EV150漏报/85误报，不是新主指标 |
| 四类通用条款的140条EC遗漏都未收到技能 | CONTRADICTED | 全部对应原HTTP有明确程序；占173条漏报的80.9%，不是案件/F1损失占比；256个末库完整messages/schema/generation均与实际调用核同 |
| EV金额不足只是缺少金额规则 | CONTRADICTED | 全部八个俄勒冈(p)金额错输出400美元，题面值明确低于400且目标相同，已送规则要求取较小者；不能据此识别注意力/表示方式等因果原因 |
| 八个OR(p)金额错误全是末尾JSON损坏或都由B6新引入 | CONTRADICTED | 六个保存推理计划已写错，八个同资产联邦(d)(5)金额正确；实际B5父库是5正确变错/2漏报/1已错。全67目标主张另有14低值正确、14漏报、31上限正确；不是67独立案件或新指标，不证明单一措辞根因 |
| 末库已经做过人工法律专家验证 | UNSUPPORTED | 仅助手全文与公开数值来源审查；七记录/五EC七EV/operators空，18种美元数值有公开额度或组合来源，不能证明法律适用或排除过拟合 |
| EV指导变化与收益可复核 | VERIFIED | 96案75案改变、45好8坏22平；其余21案真实请求/回答/评分与B1相同；观察分解非因果 |
| 教师真有正确TRAIN答案及真实父观察 | VERIFIED | 15次教师、896个含重复任务标签条目逐项核同；无未来/TEST标签 |
| 分量组合与技能修改真实参与训练 | VERIFIED | 14非NOOP提案，9接收中5次整提案未过但分量组合获收；7创建14更新，0实际删除/合并 |
| 单一组合库不是逐案挑答案 | VERIFIED | 九次实际组合1152个重复TRAIN任务视图，按公开分量统一取父/提案侧；401原响应逐项复核，重新解码评分，组合新增生成0，均值分解恒等式通过 |
| B8新增WI技能影响了无关州案件 | CONTRADICTED | 九个新金额错是六个WI可选案件的联邦条款；全部229条EC/非WI-EV请求/原回答/分数不变，10个WI额度错确实修正，负面记录不删 |
| 最终B8新增技能已在更晚TRAIN得到验证 | UNSUPPORTED | B8后新增WI EV，尚无更晚TRAIN批次；末库效果须隔离评价 |
| 原生评分与完整输出审计的口径已明确 | VERIFIED | 不改变原评分；原EC负资产使满分低于1，完整输出为独立次要口径，不把两者当同一指标 |
| 当前八批无效、必须换法律任务 | UNSUPPORTED | 未发现使主轨迹作废的问题；当前对照修正不影响原主训练 |
| 已胜成熟ACE、静态与其他经验方法 | PENDING | 完整ACE/静态首答及Text同阶段TRAIN拟合已齐；独立重复与最终16臂TEST未齐，不能把TRAIN优势冒充隔离胜出 |
| 同进度前五批完整80来源的比较可核 | VERIFIED | 主方法原EC/EV81.83457/76.77827%、强空库61.55704/62.82837%、原生ACE58.63765/55.74887%；含B1，全160任务/臂原评分重算，不是完整8批/末库/TEST或显著性 |
| 主方法教师次数少就代表所有计算都更省 | CONTRADICTED | 前五批实际8B616、教师10；ACE保留548/252，另退役10/12。主585实际被学习/首答引用、31只供B1评测，不减总616、不按逻辑记录估成本；教师输入/输出分别2114578/36942与ACE6855324/231688 |
| 主方法与ACE之间的差异完全是记忆算法差异 | UNSUPPORTED | 原生ACE B1空记忆59.53/55.30%，直接空库63.45/66.35%；生成提示/外包装不同，正式比较须保留该解释边界 |
| ACE v3失败文本交给教师的方式符合上游 | CONTRADICTED | 原文只留磁盘、失败观察为null；上游向Reflector传gen_response。已针对性修复 |
| v4仍把不完整答案修成正确答案 | CONTRADICTED | 原始失败/零分/8192上限不改，只把原公开失败文本送TRAIN反思；不恢复JSON或猜ID |
| v4接续相当于多一个独立学习重复 | CONTRADICTED | 同seed45在实际最后完整B2接续；220旧生成+102教师及64完整B3首答保留一次 |
| 接续改变了B3首答或选择较好答案 | CONTRADICTED | 全96逻辑预测同原HTTP来源、法律答案、错误与评分；两条EV截断仍为0 |
| B1/B2已受此次失败文本缺失影响 | CONTRADICTED | 348保存回答无解析失败，条件修正分支在该前缀未触发 |
| v4失败公开文本与正确TRAIN标签实际进入新教师 | VERIFIED | 固定224/228 EV的完整原文、整份反思提示/schema与fresh wire逐字一致；8192截断及原零分保留 |
| B3真实技能更新且已经交给下一批执行器 | VERIFIED | 00:29:46唯一发布，12→15条/1530tokens，3ADD旧内容不改；229 EC/EV HTTP含全部15条，EV自报引用新err-00015 |
| B3训练重答改善等于B4新案改善 | CONTRADICTED | 同案4/32→27/32完全答对；完整B4 ACE49.46/56.15%，空库54.95/57.17%，不能把拟合当迁移 |
| 完整B4同案对照及技能投递可核 | VERIFIED | 16源/每臂32任务/96逻辑记录，全部15条送达；主方法83.85/79.84%；64原调用、230EC一条8192截断零分保留，不是成熟8批或TEST |
| B4实际学习及本批成本可复核 | VERIFIED | 03:07:36唯一发布15→17条/1784tokens；32完整TRAIN、2ADD、原15内容不改；3/32→24/32同案完全答对是拟合，114native/54fresh教师，不混前批/恢复调用 |
| 完整B5首答及新技能实际投递可核 | VERIFIED | 16来源/96逻辑，ACE56.875/55.94595%、同案空库55.97222/65.3125%、原主方法86.77083/80.82837%；17条全部送达；251EV、254EC长度零分保留，64次生成端点请求、472192输入/157651输出 |
| B5的EV不足仅由格式截断解释 | CONTRADICTED | 仅1/16 EV格式零分；即使假设该值变成1，其均值上界仍为62.20%，低于空库65.31%。不是改分结果，也不单独识别原生提示、语言或记忆的因果效应 |
| B5实际发布仍未完成或必须强制增加技能 | CONTRADICTED | 05:32:56完整32TRAIN后原生0ADD，17条内容保留、计数更新，1784tokens/SHA44142a6；全链独立核同。4/32→26/32是拟合；110原生成/51新教师，两条截断零分保留 |
| B6全部96首答、实际父库与原分数已核 | VERIFIED | 07:01:38完整，原ACE62.70833/57.06019%、空库56.31055/67.72321%、主方法84.60317/83.43502%；17条全部送达，261EC/EV两长度零分保留；64生成476048输入/182121输出 |
| B6唯一发布与全部32TRAIN已独立核完 | VERIFIED | 08:18:53实际发布17→19条/1958tokens、2ADD、旧17内容保留；113原生成/54新教师、原两条长度零分保留；完整32任务及478成员双盘核验，观察1587788正常退出0 |
| B6训练改善已证明B7新案提升 | UNSUPPORTED | 4/32→24/32是同案TRAIN完全解出任务数；完整B7首答已齐，ACE64.72/43.87%、直接空库58.13/61.56%，不是两任务都获益，拟合或技能数量不证明迁移 |
| B6新库仍未实际交给后续新案 | CONTRADICTED | 第七批277EC完整HTTP已核全部19条内容/计数及原配置、无当前反思；没有读取部分分数或目标。后两批1633116只读服务等全96首答后自动核分数与使用 |
| B7完整首答及19条投递可核 | VERIFIED | 09:57:36全96独立核完、288成员双盘；ACE64.72222/43.86905%、空库58.125/61.5625%、已完成主方法同案78.54663/80.75521%；64原生成，四条长度零分保留 |
| B6两新增技能未送达或可凭自报认定有效 | CONTRADICTED | B7实际19条全送达；有效EC15/EV13回答中code18自报0/4、err19自报1/4。四失败的使用未知，非零使用或送达不证明收益，不能和未启用主方法修复混算 |
| B7唯一发布及32任务学习已完整结束 | VERIFIED | 11:40:59实际发布19→20条/2059tokens、1ADD，旧19文本保留；120原生成/60新教师，原4长度零分保留，32任务3→21完全解出是拟合；535成员自动双盘核同 |
| B7新技能已经实际交给B8但其新案收益未定 | PARTIAL | 293EC完整HTTP核20条内容/计数和新err-00020自报引用；仅核投递，不读部分分数或正确答案。B8全96首答及完整对照尚待完成，自报不证明有效 |
| 只读观察器退出意味着训练也退出或需重跑 | CONTRADICTED | 旧工具汇总89759以143退出，确切来源未定；原训练/模型/两排队句柄均未变。三个观察任务已迁服务器用户服务，实际启动和脚本SHA见launch queued.json，不更改算法、预算或模型 |
| TCPStore心跳告警意味着模型已经退出 | CONTRADICTED | 原API/engine/ACE及两等待PID、argv/start仍在，GPU97%，日志仍有生成；完整B5及新TRAIN调用继续完成。确切store-peer原因未定，没有停训或重启服务 |
| B3接续批成本可核且未重复算前缀 | VERIFIED | 原64首答+40新TRAIN生成共104native；45fresh教师；退役10/12与前两批另计 |
| 原失败成本被丢弃 | CONTRADICTED | 旧Run02完整294native/114教师双盘1643成员；退役B3的10native/12教师单列，不导入新训练 |
| 完整静态TRAIN控制已经跑出成绩 | VERIFIED | 当前run03于20:59完成128案256预测后评分；原7条/2411tokens不变、0新教师、256stop/0格式错，EC/EV 61.73%/62.38%；不是最终TEST |
| 同接口文本对照已自动衔接且已完成学习 | VERIFIED | 24日12:03完整512native/321教师、最终一文件3182tokens、256拟合及两盘各2505成员完成；不是TEST，原16长度失败保留 |
| 九个后续学习profile仍可按当前代码执行 | VERIFIED | 新23日377/383/378文件版本冻存双盘，02:30当前字节/50packages匹配，全未启动；旧22日版保留不再作启动入口 |
| 为提前比较而改了文本学习算法 | CONTRADICTED | 只把无关前序学习器数量8→2，运行时自然完成/无failure/保全/同锁检查保留；归纳/合并/翻译/执行AST未改，13合同及算法字段核验通过 |
| 三次独立学习、两项消融已完成 | PENDING | 主/ACE/Text seed45完整；whole-bank45运行，其余七个学习profile未启动，不以CPU结构检查替代 |
| Trace2Skill对照是原工具式作者复现 | UNSUPPORTED | 首seed已完整但仍是text-analysis/OpenExempt任务适配，不是原工具式ReAct分析员；差异、成本和失败均须披露 |
| 已优于SkillCommit/全部SOTA | UNSUPPORTED | 最近邻只作机制/引用比较，未量化复现；custom profile不能裸比分数冒充官方Advanced榜单 |
| 正式评价实现已接入v4与同一学习器接续来源 | VERIFIED | 核心4acdae2通过83合成；81333d9保留来源/原空库/最后B2/1301哈希/全B3与退休成本检查，准备并发调度并约束相同端点；真实TEST未读 |
| 完整评测的并发加速已经实际部署 | PARTIAL | 隔离入口106项CPU检查20.81s通过，原stdout存档，13执行器副本/11profile/50packages匹配；默认串行保留，当前单序列环境拒绝四请求模式。尚无真实四并发配置、服务切换或实测速度 |
| 正式16-arm TEST矩阵现在已经可运行 | PENDING | 所有实际末库/重复尚未齐；唯一正式CLI拒绝不完整设计，不能启动TEST |
| 相关工作已补机制分类及四条主来源 | VERIFIED | v0.10中英两主题，原四文献逐字保留；新增ExpeL/工作流记忆/ReasoningBank/兼容性审计，不表示已复现新增方法；摘要/方法/结果/表/科学数字不改，41链接及11绑定通过 |
| 已有可直接审阅的完整双语PDF | VERIFIED | 内部审阅20页含附录D，330文本单元/6表/两幅已有图，实际PDF文本差异0、关键页检查；源M/D逐字v0.10、待填高亮，不是正式投稿版或实验已完成 |
| 真实TEST已经用于调优 | CONTRADICTED | 目前只允许字节哈希；语义/标签/预测/结果未读，无验证集 |

## 已完成证据入口

以下均在`artifacts/research/openexempt_legal_scope_20261020/`，不是新模型调用：

- `Run03_learning_curve_complete_first8_final8_publications_20261022.json`
- `Run03_complete_B1_B8_actual_terminal1158_15_cost_20261022.json`
- `Run03_complete128_first_forecast_actual_skill_projection_vs_own_B1_736_native_record_delivery_and_newcase_effect_decomposition_20261022.json`
- `Run03_all15_teacher14_candidate8_publication_actual_scope_composition_and_library_management_accounting_20261022.json`
- `Run03_all9_actual_compositions1152_TRAIN_views_public_side_raw_reuse_fresh_decode_and_mean_identity_20261023.json`
- `Run03_B8_ten_WI_repairs_and_nine_federal_errors_same_WI_cases_no_nonWI_case_interference_clarification_20261023.json`
- `Run03_all_postB1_EC11_changed_components8_proposals_actual_parent_scope_gate_failure_bottleneck_20261022.json`
- `Run03_all128_TRAIN_native_target_self_F1_ceiling_and_residual_headroom_20261022.json`
- `Run03_all11_EC_actual_changed_guidance_and_all_TRAIN_claim_transitions_raw_delivery_NOT_causal_20261023.json`
- `Run03_all15_actual_teacher_payload_sizes_and896_duplicate_legal_control_views_alias_metadata_disclosed_NOT_quality_cause_20261023.json`
- `ACEv3_Run02_B3_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261022.json`
- `ACEv3_Run02_B3_failed_public_output_reflector_data_loss_safe_stop294_114_and_valid_prefix_evidence_20261022.json`
- `ACEv3_Run02_last_completed_B2_and_complete_B3_first_forecast_continuation_receipt_20261022.json`
- `ACEv4_actual284_102_prefix_and_all96_unchanged_B3_forecasts_failed_public_trace_CPU_audit_20261022.json`
- `ACEv4_actual224_228_failed_public_text_correct_targets_full_fresh_teacher_wire_verified_20261023.json`
- `ACEv4_Run03_B3_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_Run03_actual_B3_three_ADD_and_first_B4_source229_all15_verbatim_delivery_NOT_scores_20261023.json`
- `ACEv4_Run03_B4_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261023.json`
- `ACEv4_Run03_B4_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_Run03_B5_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261023.json`
- `ACEv4_Run03_B5_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_B5_full96_new_bullet_uses_EV_format_bound_and_nonterminal_NCCL_warning_observation_20261023.json`
- `Run03_final_B8_bank_complete128_TRAIN_replay_reference_for_mature_text_NOT_prequential_or_TEST_20261023.json`
- `Run03_final128_TRAIN_all256_exact_complete_output_residual_claim_inventory_NOT_new_metric_or_causal_20261023.json`
- `Run03_final128_raw_delivery140_explicit_general_omissions_and8_public_value_cap_errors_NOT_causal_20261023.json`
- `Run03_final7_skill_content_public_caps_vs_blind_static_assistant_review_v02_20261023.json`
- `Run03_vs_ACEv4_complete_B1_B5_equal80_prequential_original_metrics_and616_548_retired10_12_cost_NOT_final_TEST_20261023.json`
- `Run03_complete128_all1158_native_core_vs_fixedB1_only_actual_role_attribution_not_counterfactual_20261023.json`
- `Run03_complete128_actual1077_core81_B1only_cost_role_analysis_dual_preservation_20261023.json`
- `Run03_final128_ORp_all67_claims_wrong8_correct14_parent_regression5_and_saved_reasoning_NOT_causal_20261023.json`
- `ACEv4_Run03_B6_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261023.json`
- `ACEv4_Run03_B6_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_actual_complete_B6_learning_and_first96_auto_dual_preservation_20261023.json`
- `ACEv4_Run03_firstB7_277EC_actual_B6_all19_full_payload_not_scores_20261023.json`
- `ACEv4_Run03_B7_complete96_native_wire_raw_v14_metrics_bullet_use_and_cross_run_empty_control_audit_20261023.json`
- `ACEv4_actual_complete_B7_first96_automatic_dual_preservation_20261023.json`
- `ACEv4_Run03_B7_unique_actual_publication_all32_TRAIN_failed_public_text_exact_reflections_counters_ADD_and_true_union_cost_audit_20261023.json`
- `ACEv4_actual_complete_B7_publication32_and_first96_automatic_dual_preservation_20261023.json`
- `ACEv4_Run03_firstB8_293EC_actual_B7_all20_full_payload_not_scores_20261023.json`
- `prospective_priority_first_common_actor_text_full9_new_profiles_frozen_no_active_change_20261023.json`
- `prospective_priority20261023_operational_semantics_early2_legacy8_canonical_entry_source_validation_20261023.json`
- `hourly0230_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `implemented_method_figure_v03_actual_source_visual_links_vector_and_unchanged_v06_curve_QA_20261023.json`
- `manuscript_v07_exact_tables_abstracts_refs46_points_composition_scope_and_priority_source_QA_20261023.json`
- `manuscript_v08_evidence_led_main_complete_lineage_D_exact_tables_abstracts_refs46_points_QA_20261023.json`
- `text45_after_exact_static_run02_waiter1130167_dual_queued_no_active_budget_change_20261023.json`
- `hourly0330_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0530_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0630_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0730_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0830_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly0930_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly1030_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `hourly1130_ACEv4_Run03_actual380_priority9_377383378_static400_original_handles_direction_20261023.json`
- `source_key_metadata_only_train308_sealed128_disjoint_revalidation_NOT_semantic_TEST_or_performance_20261023.json`
- `source_key_metadata_only_train308_sealed128_revalidation_dual_preservation_20261023.json`
- `Run03_actual15_teacher_context_no_logged_compaction_vs_explicit1024_tail_delivery_NOT_quality_cause_20261023.json`
- `Run03_actual15_teacher232_witness_delivery_source_filter_loss_true_harm_actual_HTTP_v02_NOT_causal_20261023.json`
- `isolated_v2_teacher_delivery_all15_actual_history232witnesses_restored21_self_describing_alias_v02_NOT_performance_20261023.json`
- `isolated_v2_final6cbc_actual_entry_binding_guard_and_exact719_teacher_pack_AST_QA_NOT_performance_20261023.json`
- `teacher_delivery_candidate_final6cbc_complete_git_three_heads_dual_20261023.json`
- `teacher_delivery_candidate6cbc_B7firsts_context_and_checkpoint_scoped_dual_preservation_20261023.json`
- `manuscript_v010_related_work_primary_refs_exact_v09_scientific_body_11profiles_QA_20261023.json`
- `frozen_eval_four_worker_cpu105_exact_cache_failure_drain_active11_unchanged_serial91h_scenario_NOT_deployed_20261023.json`
- `frozen_eval_parallel_dispatch_endpoint_bound_final_CPU_check_stdout_20261023.json`
- `frozen_eval_four_worker_cpu106_endpoint_exact_cache_drain_active11_unchanged_NOT_deployed_20261023.json`

## 论文与剩余实验

[当前初稿v0.10](manuscript_v1_20261021.md)和[实验附录D](appendix_experimental_details_20261022.md)
描述真实直接回答、标签辅助、公开法律作用域提交与有界TRAIN反馈。
[完整v0.6](revisions/manuscript_v06_20261023_0235.md)及其附录D逐字保留。
[完整v0.7](revisions/manuscript_v07_20261023_0259.md)及其附录D也逐字保留。
[完整v0.8](revisions/manuscript_v08_20261023_0452.md)及[同期附录D](revisions/appendix_D_v08_20261023_0452.md)逐字保留。
[完整v0.9](revisions/manuscript_v09_20261023_0627.md)及[同期附录D](revisions/appendix_D_v09_20261023_0627.md)也已逐字保留。
图1完整46个F1点/六条折线坐标不改，B8发布状态已更新，SVG/PDF/600dpi PNG可用。
[方法总览与双语图注](figures/method_overview_caption_20261023.md)另行完成，明确标签释放
时机、全部已见TRAIN重放、公开编辑依赖、分量组合与下一批使用；无新成绩/虚构分组。
Georgia不可用，沿用图1实际DejaVu Serif；图像、两版摘要和所有表行不变。
v0.7补真实组合/成本证据、纠正B8法条与案件范围歧义及更新未来操作顺序；
v0.8将源码与适配器修复沿革归入附录，正文突出方法及实际收益，所有指标不变，待整合图号。
v0.9精简正文的内部版本前言，明确1158只计生成端点HTTP，不含分词和就绪查询；
不改任何科学效果、生成成本数值、摘要、表、图或参考文献。
v0.10补两主题相关工作及ExpeL、AWM、ReasoningBank、执行兼容性审计四条已核主来源；
旧四条参考文献保留，摘要、方法、结果和表及所有科学数值逐字不变，附录正文不变。
它不新增实验臂，也不借引用声称已复现或验证这些方法；41条本地链接及11绑定匹配。
[内部双语PDF](../artifacts/research/manuscript_review_20261023/v010_bilingual_internal_v03/legal_skill_evolution_v010_bilingual_internal_review.pdf)
完整保留上述源稿及附录D，既有两图嵌入，20页是合排审阅长度，不是英文投稿版页数。
[最终图文核对](../artifacts/research/manuscript_review_20261023/v010_bilingual_internal_v03/final_review_QA_20261023.json)
绑定源稿、PDF、330文本单元/6表、字体、关键页和重现程序，不改数据或学习链。
正文不以工程组件、更多技能或接口支持操作数冒充创新；近邻机制须正确归属。
已核实参考条目不因润色改标题或作者；新引用仍须主来源核实。

最终计划16arms、5比较家族×EC/EV=10主要比较、两单seed消融×EC/EV=4次要比较。
128来源配对bootstrap20000，PCG64seed2026102192；区间条件于实际库和固定评价seed45。
不把3库变成384来源，不从单轨迹造学习误差带或显著性。
全部真实末库/完整矩阵/统计与评价源码必须在第一条TEST预测前冻结。
当前4096逻辑预测按主Run文件区间均值作不复用串行情景为91.58h，不是实际TEST
耗时或ETA。隔离调度准备不减少16臂/128来源或推理预算，也未改变当前模型服务。

完整ACE与静态TRAIN后先完成共同执行器Text45，再投入其他重复。若TRAIN证据
不足以支持方法收益，就继续TRAIN根因优化与新运行，
并重新完成受影响的正式学习比较。论文写作与这些实验并行，不能只停在清单、
历史审计或等待结果，也不能提前填上尚未得到的优越性结论。

Text是离线构建，未来的末库TRAIN拟合必须与本方法实际末库的完整128来源重放
对齐，不能直接与各批当时的在线首答比较。现有B8组合已提供全256任务参照，
原F1 EC86.03/EV89.30%，新增生成为零；本方法已在这些样本上准入优化，
因此该比较偏向本方法，只作TRAIN诊断，不替代原曲线或正式TEST。

## 2026-10-23下午：当前来源交接、失败反馈与更细提交证据

本段记录v0.12整合前的核对；v0.11正文、附录D、两图和内部审阅PDF均按原字节
保留。没有新增主方法训练分数，不等于原有正向收益失效。正式主表仍待隔离测试，
不填入TRAIN成绩。当前稿件版本见下一节。

- [16条件/12源配置的实际协议与十主要四次要比较核对](../artifacts/research/openexempt_legal_scope_20261020/final16_current_lineage_actual_source_protocol_primary10_secondary4_plan_NOT_TEST_config_20261023.json)：
  使用真实配置验证一致协议与自身B1配对，三个故意错配均拒绝；不是未完成末库
  已合格，也不是可执行TEST配置。
- [当前矩阵与执行交接](../docs/research/OPENEXEMPT_FINAL_MATRIX_CURRENT_LINEAGE_20261023.md)：
  ACE04→静态03→Text45→两项消融和其余重复均有实际后台等待器。后续尚未开始
  的阶段不称训练中，失败不当完成，不按表现选库或重试。Test未自动启动。
- [B8全部两条原截断的失败反馈原样投递](../artifacts/research/openexempt_legal_scope_20261020/ACEv4_Run04_B8_all2_original_truncations_zero_preserved_full_public_text_correct_target_exact_fresh_reflection_20261023.json)：
  295EV/302EV原8192截断零分保留，实际教师收到完整原文与正确本案TRAIN目标。
  96条首答除真实复用元数据外逐项相同；复用不是新生成。16成员原始证据已双盘保存。
- [完整14候选的法域分量与任务级门槛区别](../artifacts/research/openexempt_legal_scope_20261020/Run03_all14_actual_component_vs_task_gate_decisions_and_B1C2_Illinois_EV_rescue_NOT_independent_ablation_20261023.json)：
  九次接收中五次原整库提案未过，四次接收后的库在结构上不同于只按任务选取的
  组合；B1C2实际保留一个整EV门槛未通过的IL分量。三个已见TRAIN来源的原EV
  F1由57.41%变79.63%，不是新案/TEST或独立task_local学习结果。

[机制结果段及完整边界](method_scope_and_failure_decisions_20261021.md)按师兄实验skill
组织，并用nature-paper区分局部TRAIN改善、固定提案结构比较与真正独立消融。
未增加新臂、种子、模型或运行框架，不把已有通用重放或源保持机制算作独创。

## 历史内部审阅稿v0.12：ACE45自然完成、来源/成本齐全

ACE45接续Run04于10月23日15:48:37自然完成全部八批。唯一末库21条/2158tokens，
旧20条内容保留；新增一条复合资产中心名词/修饰词的类别判定程序，不是逐案答案表。
这是助手内容审查，不是法律专家验证，也没有更晚TRAIN验证该末次更新。
[完整末库及嵌套来源核验](../artifacts/research/openexempt_legal_scope_20261020/ACEv4_Run04_actual_complete_bank_nested_origin_final21_content_and_all3_terminal_archives_QA_NOT_TEST_20261023.json)
按真实completion通过，三个学习沿革的两盘终态档均核原hash。仅这一来源合格，
不代表16臂矩阵或其余尚未完成的学习已合格。

[实际完整成本](../artifacts/research/openexempt_legal_scope_20261020/ACEv4_Run04_complete128_terminal_actual_retained_and_retired_B3_B8_cost_NOT_TEST_20261023.json)：
保留896native/423成功教师；加旧B3的10/12及旧B8的5/7，合计911native、
442成功教师、443attempts。一份超时usage未知，不计为0。8B输入/输出
7258239/2304128，已知教师输入/输出11984697/427053为下界，推理129574已含输出。
B8全部32条真实反思、原生计数与ADD核验通过，同案完全正确5→25只是拟合。
静态TRAIN对照已于15:49:13实际开始；Text45与后继八stage仍是等待器，额度3349未扩。

[v0.12主体](manuscript_v1_20261021.md)和[附录D](appendix_experimental_details_20261022.md)
只整合完成状态、实际成本及上述细粒度提交证据；摘要、引言、相关工作、数据、方法、
两张主结果表的原始数值、B3–B8投递分解、正式待填节、讨论和八条文献保持原样。
[源稿核对](../artifacts/research/openexempt_legal_scope_20261020/manuscript_v012_actual_ACE_terminal_and_scope_evidence_protected_main_science_tables_refs11profiles_source_QA_20261023.json)
验证47条本地链接、旧v0.11精确快照和11个活跃/后继冻结配置仍匹配。

[当前双语内部审阅PDF](../artifacts/research/manuscript_review_20261023/v012_bilingual_internal_v01/legal_skill_evolution_v012_bilingual_internal_review.pdf)：
21页、339文本单元、6表、2原图，所有源非空行都有呈现，实际PDF文本/坐标核对差异0。
[最终审阅QA](../artifacts/research/manuscript_review_20261023/v012_bilingual_internal_v01/final_review_QA_20261023.json)
绑定完整源稿、渲染程序、字体、PDF和1/11/12/20页实际视觉检查，未见重叠/裁切。
这是内部审阅，不是期刊模板、法律专家审查或可投稿定稿。正式TEST、其余控制、
三次学习变异和两项独立消融仍待完成；待填结果保留黄色，不填0或TRAIN成绩。

## 同行结构与贡献核对，17:09补齐，不是新性能结果

[十篇同行写法研究v1](../peer-papers/同行写法研究-v1-20261023.md)及
[固定来源/全文哈希/逐句统计清单](../peer-papers/20261023-scope-consolidation/source_manifest.json)
补足最近邻、术语、方法差异和现有实验覆盖。原文为私有阅读缓存，不作为代码复现
或公开转载；未改正文、附录D、PDF、方法、16条件或后台队列，0模型/教师/TEST调用。
采用师兄paper-related-method、paper-ideation与实验skill组织建议，不按模板增加
多轮咨询、验证集、新模型或未经核实的比较成绩。当前仍须完成真实后继实验。

## 当前内部审阅稿v0.13：完整静态TRAIN对照与实际Text交接

静态Run03于2026-10-23 20:59:00 CST自然成功结束，所有256预测先于评分，原零案件
7条/2411-token库不变。完整同128来源的EC/EV F1为61.73%/62.38%，相较空库
+1.56/−0.54pp；主方法在线首答82.03%/79.16%，分别高20.30/16.78pp。
B2–B8每批两端点均高于该固定库；这些是单流TRAIN描述，不是等效性检验、最终
冻结库比较、跨学习重复区间或正式TEST。原先三个条件的数值和八批曲线不改。

[全256原始来源、配对收益/损害、失误清单、成本及交接](../artifacts/research/openexempt_legal_scope_20261020/static03_complete128_256_predictions_actual_metrics_residuals_cost_dual_preservation_and_Text45_handoff_NOT_TEST_20261023.json)
核对全量native/complete-output原分数。静态→主方法首答的EC漏引432→221次、
EV漏引390→209次；EV金额错配50→67次，不能把整体优势写成数值执行全面改善。
这些是主张出现次数，不是独立案件，不改主终点。两盘终态档各789成员均逐项hash
核验，device不同；成本256次8B/256HTTP、1836443输入/640206输出、0新教师，
约5h10m执行与评分墙钟。早期静态编译成本另行保留，不冒称整个对照无需教师。

Text45按原计划于20:59:19从等待转入真实源轨迹生成，21:12快照9/256、0教师。
它先独立保存全部预测再释放标签，不复用主方法或ACE的答案/技能；额度3991是已执行
的共享预约上限，不是实际调用量。后继八stage仍等待Text，不自动开启TEST。
当前证据支持继续现行主方法、共享执行器文本对照、既定消融与独立重复，不换任务、
不自动采用教师交付候选，也不扩大16条件或改变统计规则。

[v0.13正文](manuscript_v1_20261021.md)与[附录D](appendix_experimental_details_20261022.md)
仅整合完整静态证据及真实状态；[源稿QA](../artifacts/research/openexempt_legal_scope_20261020/manuscript_v013_complete_static_TRAIN_source_protected_science_tables_refs11profiles_QA_20261023.json)
确认只改评价节与5.4、新增静态行，原Table1/2行、摘要至方法、其他结果、讨论、文献
及待填标记保持，11个当前/后继冻结配置的426个不同绑定文件均不变。
精确旧源稿见[v0.12正文快照](revisions/manuscript_v012_before_static_complete_20261023.md)
与[旧附录](revisions/appendix_D_v012_before_static_complete_20261023.md)。

[当前双语21页内部审阅PDF](../artifacts/research/manuscript_review_20261023/v013_bilingual_internal_v01/legal_skill_evolution_v013_bilingual_internal_review.pdf)
含347文本单元、6表、2原图，PDF文本/坐标差异0，实际视觉检查1/12/13/20页。
[最终QA](../artifacts/research/manuscript_review_20261023/v013_bilingual_internal_v01/final_review_QA_20261023.json)
保留黄色正式TEST/重复/消融待填；不是可投稿定稿。师兄实验skill组织结果与研究问题，
nature-paper约束训练/正式证据边界；旧v0.12 PDF和源稿、所有原始失败均保留。

## 23:37执行更新：论文证据优先及结果合理性

用户要求不忘主线、继续论文工作。原生Goal保持active，执行更新见
[当前入口](../docs/CURRENT_GOAL.md)。现有v0.13已写入的结果不因后台计数变化反复
重排；下一次结果段更新应来自真实完成的对照或重复，而不是新的启动成功检查。
本节是工作清单，不改正文数值、图或正式TEST待填。

| 论文主张 | 已有完整证据 | 下一项必要证据及解释边界 |
|---|---|---|
| 技能能帮助冻结8B | 全128 TRAIN首遇相对强空库EC/EV +21.86/+16.24pp | 末库共同TEST及三次真实学习；不把TRAIN当正式主表 |
| 后续学习有额外收益 | 全112后续TRAIN相对自身B1 EC/EV +0.86/+9.39pp | 报出EC小增益，不把EV结论写成两任务同等持续进化 |
| 学习库不同于固定法条摘要 | 原固定库全256预测及配对损害已核；主首答两端点领先 | 固定库EV略低于空库是有效结果，不强改为预期排序或泛称静态方法无效 |
| 优于经验学习适配 | ACE完整首遇TRAIN已齐，Text独立构建正在进行 | 比较末库而非把Text末库重答与在线冷启动首答混比；适配、语言及成本差异如实保留 |
| 机制与技能管理有效 | 7CREATE、14UPDATE、14候选接收/拒收来源及实际投递已核 | 两项独立学习消融及最终冻结结果；0DELETE/MERGE不写成发生过的管理收益 |

合理性核对以原生案内F1再按来源平均，完整独立n为128，不把EC/EV视图或三个库
扩成256/384独立案件。F1不是由平均P/R重新计算；EC原生TRAIN上限96.88%而
非所有案件均100%，但这不能解释掉B3–B8尚有11.94pp的EC残余空间。
完整输出辅助审计不替换主终点，原无效分数不排除。EV漏引减少而金额错配未同步
改善，故当前证据支持较完整的法律依据覆盖，不支持数值计算已全面可靠。

ACE23.58h的实测沿革已分解为原生长生成及教师调用；为六个尚未开始的145/245
构建准备共同提速，不热改当前Text或两项45消融。隔离版已接入保序调度及精确源码
核验，206项维护中的CPU契约25.16s通过；这是调度/来源准备，不是性能突破。
实际GPU加速、六份新环境配置和自动边界交接仍未完成，旧队列仍有效。

## 2026-10-24 02:50：Text源语料封存与真实教师内容，不是性能结果

Text45已完成全部256个独立物理源回答，128来源、EC/EV成对；源阶段全部空库、
stop、无解析/执行错误，实际输入1,621,981、输出699,309tokens。其解析及评分与
原强空库逐项相同，实际调用路径/响应ID全不同；同seed的新调用不能当成新的统计
重复。全部源预测及封存早于首个教师请求，两盘各774成员归档已由现有观察器核验。

[22份实际教师输入、编辑与成本核对](../artifacts/research/openexempt_legal_scope_20261020/Text45_sealed256_actual_own_sources_teacher_prefix22_input_content_target_resolution_and_cost_NOT_skill_gain_or_TEST_20261024.json)
确认教师拿到了自己的真实公开输入、完整回答、训练目标和原生反馈，无工具或结果
缓存复用。20份独立CPU预览可应用，2份使用简写标题、须由既定最终翻译解析位置；
未修补、删除或按预览挑选中间编辑。实际编辑含一般/特定豁免并行核对、资格与金额
上限区分、独立资产-条款金额规则。当前只有中间构建，尚不能说明8B调用收益。
22份已返回教师成本为464,771输入/29,556输出，14,773推理已含于输出，不能再相加。

继续原流程及新有限接续队列，保留原主方法。最终Text TRAIN末库应与主方法末库
完整重答86.03/89.30对齐，而非在线首答；正式TEST与六项独立构建仍未完成。
本次未改v0.13正文/附录/PDF、评分或推理链路，无新增模型、教师、tokenizer或TEST调用。

## 2026-10-24 05:08：Text全部256教师完成，实际合并开始，尚无性能结果

[完整教师输入、实际成本及首5组合并](../artifacts/research/openexempt_legal_scope_20261020/Text45_all256_actual_teacher_inputs_cost_and_first5_merge_groups_NOT_final_skill_gain_or_TEST_20261024.json)
逐项核对全部256真实请求与各自源输入、8B原始响应、解析、原生TRAIN反馈和目标；
源制品与已封存manifest相同。每次均为原教师新调用、无工具、无重试，原始日志
及唯一预约可追溯。34个success/222个failure按完整输出FP=FN=0定义，不是平均
F1或新技能准确率。392项中间编辑不能当成392个已发布技能。

实际分析成本5,300,047输入/351,855输出，181,380推理已含于输出，2,594,688缓存
输入已含于输入。首末调用跨度8,713.061845s；不是8B GPU忙时或完整方法总成本。
05:03快照的前5组合并输入均与冻结顺序一致，首组含6份及最后一个小尾输入；
每个源修改都在完整分组计划中恰好出现一次，不按成绩筛选。仅前4组合并响应
已在本次快照中观察，51+10+2+1仍是全计划，不能写成全部合并已完成。

首份真实合并保留了适用法域、事实条件、一般/特定豁免、额度与资格及配对/分配
边界。第三组仍保留简写章节位置，CPU预览不能直接落地，需由原预定最终翻译
解析；没有额外修复、结果筛选或原始文件改写。原客户端以规范化JSON包装计算
事件日志哈希，初次审计误用裸字符串的断言已按此原契约更正，256项全部匹配。

师兄实验与数据skill用于将实际机制、成本和未完成证据分开记录。当前不是最终库、
弱模型调用收益、独立新案或TEST结果；不改v0.13数值、主方法、16条件或测试边界。

## 2026-10-24 05:55：Text实际最终库、完整构建链和真实失败，不是F1结果

[完整321调用/64合并/最终翻译/实际EC与EV投递](../artifacts/research/openexempt_legal_scope_20261020/Text45_complete321_published3182tokens_full64_merges_actual_EC_EV_delivery_and_EV_length_NOT_F1_or_TEST_20261024.json)
确认51→10→2→1的全部真实组输入、顺序、原初始坐标及层间屏障。最终翻译正文
与最后合并完全相同，严格应用和actor_bank均重现05:44:31发布物。最终1文档、
71行、3182tokens，无引用附件、数值operator或案件答案表；是Text适配末库，
不是主方法库从7条改为1条。主方法、冻结推理条件和16条件计划不变。

全部教师实际6,429,967输入/503,252输出，218,269推理已含于输出，3,318,528缓存
输入已含于输入；321次成功响应/321次尝试、无工具或结果缓存复用。8B源生成及
正在进行的末库重答成本另列，不能将这些教师总量说成全部方法计算或GPU小时。
现有观察器两盘各完整验证1738个最终构建成员，后自然成功退出；外层hash和
963个教师原始制品均与实际文件核对，全部历史失败继续保留。

首个EC/EV实际输入与原actor_payload逐字相同，完整接收最终技能；没有当前标签、
隐藏数值求解或答案修复。首个EC正常stop2621tokens，首个EV为length8192并保留
不完整输出错误。05:54观察的6份已完成输出为5stop/1length，不是全量F1或失败率
结论。此为真实模型预算失败，不调整单臂预算、重抽、修复或剔除；待完整256重答
后按原评分处理，不能因对照开头不利便停止有效对照。

师兄实验与数据skill用于区分构建完成、完整投递、真实失败与尚未证明的有效使用。
仅输入一致不能证明模型遵循了程序；尚不写Text优劣、未见新案收益、TEST或显著性。
v0.13及正式主表待填保持，下一步是完整末库TRAIN和已排队的消融/独立构建。
